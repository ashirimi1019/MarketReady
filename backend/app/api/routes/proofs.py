from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from uuid import uuid4
from pathlib import Path
import os

from app.api.deps import get_db, get_current_user_id
from app.schemas.api import PresignIn, PresignOut, ProofIn, ProofOut
from app.models.entities import Proof
from app.core.config import settings
from app.services.storage import (
    create_presigned_upload,
    is_s3_object_url,
    resolve_file_view_url,
    s3_is_enabled,
)
from app.services.ai import (
    verify_proof_with_ai,
    _log_ai_audit,
    ai_is_configured,
    get_active_ai_model,
)
from app.models.entities import ChecklistItem, StudentProfile

router = APIRouter(prefix="/user/proofs")


def _is_certificate_proof_type(proof_type: str) -> bool:
    normalized = (proof_type or "").strip().lower()
    return normalized == "cert_upload" or "cert" in normalized


def _is_uploaded_document_url(url: str) -> bool:
    if url.startswith("/uploads/"):
        return True
    return is_s3_object_url(url)


def _serialize_proof(proof: Proof) -> dict:
    return {
        "id": proof.id,
        "checklist_item_id": proof.checklist_item_id,
        "proof_type": proof.proof_type,
        "url": proof.url,
        "view_url": resolve_file_view_url(proof.url),
        "status": proof.status,
        "review_note": proof.review_note,
        "proficiency_level": proof.proficiency_level or "intermediate",
        "metadata": proof.metadata_json if isinstance(proof.metadata_json, dict) else None,
        "created_at": proof.created_at,
    }


@router.post("/presign", response_model=PresignOut)
def presign_upload(
    payload: PresignIn,
    user_id: str = Depends(get_current_user_id),
):
    if not s3_is_enabled():
        raise HTTPException(status_code=400, detail="S3 bucket not configured")
    try:
        return create_presigned_upload(user_id, payload.filename, payload.content_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/upload")
def upload_file(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    base_dir = Path(settings.local_upload_dir) / "proofs" / user_id
    base_dir.mkdir(parents=True, exist_ok=True)
    safe_name = os.path.basename(file.filename or "proof")
    filename = f"{uuid4().hex}_{safe_name}"
    file_path = base_dir / filename
    with file_path.open("wb") as buffer:
        buffer.write(file.file.read())
    return {"file_url": f"/uploads/proofs/{user_id}/{filename}"}


@router.get("", response_model=list[ProofOut])
def list_proofs(
    checklist_item_id: str | None = None,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    query = db.query(Proof).filter(Proof.user_id == user_id)
    if checklist_item_id:
        query = query.filter(Proof.checklist_item_id == checklist_item_id)
    proofs = query.order_by(Proof.created_at.desc()).all()
    return [_serialize_proof(proof) for proof in proofs]


@router.post("", response_model=ProofOut)
def register_proof(
    payload: ProofIn,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    checklist_item = db.query(ChecklistItem).get(payload.checklist_item_id)
    if not checklist_item:
        raise HTTPException(status_code=404, detail="Checklist item not found")

    certificate_mode = _is_certificate_proof_type(payload.proof_type)

    if certificate_mode and not _is_uploaded_document_url(payload.url):
        raise HTTPException(
            status_code=400,
            detail="Certificate proofs require a document upload. Upload a file instead of submitting a URL.",
        )
    if certificate_mode and settings.ai_strict_mode and not ai_is_configured():
        raise HTTPException(
            status_code=503,
            detail="AI strict mode is enabled; certificate verification requires active AI configuration.",
        )

    proof = Proof(
        user_id=user_id,
        checklist_item_id=payload.checklist_item_id,
        proof_type=payload.proof_type,
        url=payload.url if certificate_mode else (payload.url or "self_attested://yes"),
        proficiency_level=payload.proficiency_level or "intermediate",
        metadata_json=payload.metadata,
    )
    if not certificate_mode:
        proof.status = "verified"
        proof.review_note = (
            "Self-attested completion accepted. Certificate uploads require AI verification."
        )

    db.add(proof)
    if not certificate_mode:
        db.commit()
        db.refresh(proof)
        return _serialize_proof(proof)

    db.flush()
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).one_or_none()
    if certificate_mode and ai_is_configured() and checklist_item:
        try:
            verdict = verify_proof_with_ai(
                checklist_item=checklist_item,
                proof_type=payload.proof_type,
                url=payload.url,
                metadata=payload.metadata,
                profile=profile,
            )
        except RuntimeError as exc:
            db.rollback()
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        confidence = verdict.get("confidence", 0.0)
        meets = verdict.get("meets_requirement", False)
        decision = verdict.get("decision", "needs_more_evidence")
        note = verdict.get("note") or ""
        issues = verdict.get("issues") or []
        threshold = settings.ai_proof_verify_threshold

        if confidence >= threshold:
            if meets:
                proof.status = "verified"
            else:
                proof.status = "rejected"
        else:
            proof.status = "needs_more_evidence"

        if issues:
            note = (note + " " + " ".join(issues)).strip()
        if not note:
            if proof.status == "verified":
                note = "AI verified this proof."
            elif proof.status == "rejected":
                note = "AI could not confirm this proof meets the requirement."
            else:
                note = "AI needs more evidence to verify this proof."
        proof.review_note = note
        db.commit()
        db.refresh(proof)
        _log_ai_audit(
            db,
            user_id=user_id,
            feature="proof_verify",
            prompt_input={
                "checklist_item_id": str(payload.checklist_item_id),
                "proof_type": payload.proof_type,
                "url": payload.url,
                "confidence": confidence,
                "decision": decision,
            },
            context_ids=[str(payload.checklist_item_id)],
            model=get_active_ai_model(),
            output=note,
        )
    else:
        proof.status = "submitted"
        proof.review_note = "Queued for AI verification."
        db.commit()
        db.refresh(proof)
    return _serialize_proof(proof)
