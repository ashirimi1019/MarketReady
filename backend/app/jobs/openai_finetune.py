import argparse
import json
from pathlib import Path

import httpx

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.entities import ChecklistItem, Proof, StudentProfile

VERIFIER_SYSTEM_PROMPT = (
    "You are an evidence verifier for career pathway proofs. "
    "Decide if the provided proof likely satisfies the checklist requirement. "
    "Do not claim authenticity; only assess the evidence content. "
    "Output a single JSON object with keys: "
    "meets_requirement (boolean), confidence (0 to 1), "
    "issues (array of strings), decision (string: verified, needs_more_evidence, rejected), "
    "note (string for the student)."
)


def _require_openai_config() -> tuple[str, str]:
    api_key = settings.openai_api_key
    api_base = settings.openai_api_base.rstrip("/")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing in backend/.env")
    if not api_base:
        raise RuntimeError("OPENAI_API_BASE is missing in backend/.env")
    return api_key, api_base


def _label_from_status(status: str, review_note: str | None) -> dict:
    if status == "verified":
        return {
            "meets_requirement": True,
            "confidence": 0.95,
            "issues": [],
            "decision": "verified",
            "note": review_note or "Evidence appears to satisfy this requirement.",
        }
    if status == "rejected":
        issues = [review_note] if review_note else ["Evidence does not satisfy the requirement."]
        return {
            "meets_requirement": False,
            "confidence": 0.95,
            "issues": issues,
            "decision": "rejected",
            "note": review_note or "Evidence does not satisfy the requirement.",
        }

    issues = [review_note] if review_note else ["Additional evidence is required."]
    return {
        "meets_requirement": False,
        "confidence": 0.6,
        "issues": issues,
        "decision": "needs_more_evidence",
        "note": review_note or "Please submit stronger evidence.",
    }


def _build_chat_row(user_payload: dict, assistant_payload: dict) -> dict:
    return {
        "messages": [
            {"role": "system", "content": VERIFIER_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload)},
            {"role": "assistant", "content": json.dumps(assistant_payload)},
        ]
    }


def _build_synthetic_rows(items: list[ChecklistItem], synthetic_variants: int = 4) -> list[dict]:
    if synthetic_variants < 1:
        synthetic_variants = 1

    verified_quality = ["strong", "excellent", "comprehensive", "well-documented"]
    needs_quality = ["thin", "partial", "unclear", "insufficient"]
    rejected_quality = ["invalid", "mismatched", "off-topic", "irrelevant"]
    states = ["CA", "TX", "NY", "WA"]
    semesters = ["Year 2", "Year 3", "Year 4", "Year 5"]
    universities = [
        "Example University",
        "State Tech University",
        "Metro Institute",
        "Northern College",
    ]

    rows = []
    for item in items:
        allowed = item.allowed_proof_types or []
        valid_proof_type = allowed[0] if allowed else "writeup"
        invalid_proof_type = "unrelated_proof"
        if invalid_proof_type in allowed:
            invalid_proof_type = "generic_document"

        base_checklist = {
            "title": item.title,
            "description": item.description,
            "rationale": item.rationale,
            "tier": item.tier,
            "is_critical": item.is_critical,
            "allowed_proof_types": allowed,
        }

        for variant in range(synthetic_variants):
            profile = {
                "semester": semesters[variant % len(semesters)],
                "state": states[variant % len(states)],
                "university": universities[variant % len(universities)],
                "masters_interest": bool(variant % 2),
                "masters_target": "MS CS" if variant % 2 else None,
                "masters_timeline": "in 2 years" if variant % 2 else None,
                "masters_status": "planning" if variant % 2 else None,
            }
            variant_proof_type = allowed[variant % len(allowed)] if allowed else valid_proof_type

            verified_user_payload = {
                "checklist_item": base_checklist,
                "proof": {
                    "proof_type": variant_proof_type,
                    "url": f"https://example.edu/evidence/verified-{variant}",
                    "metadata": {
                        "summary": f"Detailed evidence demonstrating '{item.title}' with measurable outcomes.",
                        "quality": verified_quality[variant % len(verified_quality)],
                    },
                    "evidence_excerpt": (
                        f"The submission includes concrete artifacts, metrics, and outcomes for '{item.title}'."
                    ),
                    "evidence_meta": {"source": "synthetic_seed"},
                },
                "student_profile": profile,
            }
            verified_assistant_payload = {
                "meets_requirement": True,
                "confidence": 0.92,
                "issues": [],
                "decision": "verified",
                "note": "Evidence likely satisfies the requirement.",
            }

            needs_user_payload = {
                "checklist_item": base_checklist,
                "proof": {
                    "proof_type": variant_proof_type,
                    "url": f"https://example.edu/evidence/needs-{variant}",
                    "metadata": {
                        "summary": "Submission includes claims but lacks enough concrete detail.",
                        "quality": needs_quality[variant % len(needs_quality)],
                    },
                    "evidence_excerpt": (
                        "The evidence references work performed but does not clearly prove requirement completion."
                    ),
                    "evidence_meta": {"source": "synthetic_seed"},
                },
                "student_profile": profile,
            }
            needs_assistant_payload = {
                "meets_requirement": False,
                "confidence": 0.7,
                "issues": ["Insufficient detail to verify requirement completion."],
                "decision": "needs_more_evidence",
                "note": "Please provide clearer and requirement-aligned evidence.",
            }

            rejected_user_payload = {
                "checklist_item": base_checklist,
                "proof": {
                    "proof_type": invalid_proof_type,
                    "url": f"https://example.edu/evidence/rejected-{variant}",
                    "metadata": {
                        "summary": "Submitted evidence is unrelated to the checklist requirement.",
                        "quality": rejected_quality[variant % len(rejected_quality)],
                    },
                    "evidence_excerpt": (
                        "The content does not match the target skill or expected proof criteria."
                    ),
                    "evidence_meta": {"source": "synthetic_seed"},
                },
                "student_profile": profile,
            }
            rejected_assistant_payload = {
                "meets_requirement": False,
                "confidence": 0.9,
                "issues": ["Evidence type and content do not match the requirement."],
                "decision": "rejected",
                "note": "This proof does not satisfy the requirement. Submit requirement-specific evidence.",
            }

            rows.append(_build_chat_row(verified_user_payload, verified_assistant_payload))
            rows.append(_build_chat_row(needs_user_payload, needs_assistant_payload))
            rows.append(_build_chat_row(rejected_user_payload, rejected_assistant_payload))

    return rows


def export_training_file(
    output: Path,
    *,
    limit: int | None,
    min_examples: int,
    include_synthetic: bool,
    synthetic_variants: int,
) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        query = (
            db.query(Proof)
            .filter(Proof.status.in_(["verified", "rejected", "needs_more_evidence"]))
            .order_by(Proof.created_at.desc())
        )
        if limit:
            query = query.limit(limit)
        proofs = query.all()

        rows = []
        for proof in proofs:
            item = db.query(ChecklistItem).get(proof.checklist_item_id)
            if not item:
                continue
            profile = db.query(StudentProfile).filter(StudentProfile.user_id == proof.user_id).one_or_none()

            user_payload = {
                "checklist_item": {
                    "title": item.title,
                    "description": item.description,
                    "rationale": item.rationale,
                    "tier": item.tier,
                    "is_critical": item.is_critical,
                    "allowed_proof_types": item.allowed_proof_types or [],
                },
                "proof": {
                    "proof_type": proof.proof_type,
                    "url": proof.url,
                    "metadata": proof.metadata_json or {},
                    "evidence_excerpt": None,
                    "evidence_meta": {"source": "historical"},
                },
                "student_profile": {
                    "semester": profile.semester if profile else None,
                    "state": profile.state if profile else None,
                    "university": profile.university if profile else None,
                    "masters_interest": profile.masters_interest if profile else None,
                    "masters_target": profile.masters_target if profile else None,
                    "masters_timeline": profile.masters_timeline if profile else None,
                    "masters_status": profile.masters_status if profile else None,
                },
            }

            assistant_payload = _label_from_status(proof.status, proof.review_note)
            rows.append(_build_chat_row(user_payload, assistant_payload))

        if include_synthetic:
            checklist_items = db.query(ChecklistItem).all()
            rows.extend(_build_synthetic_rows(checklist_items, synthetic_variants=synthetic_variants))

        if len(rows) < min_examples:
            raise RuntimeError(
                f"Not enough labeled proofs to train. Found {len(rows)} examples, need at least {min_examples}."
            )

        with output.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row) + "\n")

        return len(rows)
    finally:
        db.close()


def upload_training_file(file_path: Path) -> str:
    if not file_path.exists():
        raise RuntimeError(f"Training file not found: {file_path}")

    api_key, api_base = _require_openai_config()
    headers = {"Authorization": f"Bearer {api_key}"}

    with file_path.open("rb") as handle:
        files = {"file": (file_path.name, handle, "application/jsonl")}
        data = {"purpose": "fine-tune"}
        with httpx.Client(timeout=90.0) as client:
            response = client.post(
                f"{api_base}/files",
                headers=headers,
                data=data,
                files=files,
            )
            response.raise_for_status()
            payload = response.json()
            return payload["id"]


def create_finetune_job(training_file_id: str, *, model: str | None, suffix: str | None) -> dict:
    api_key, api_base = _require_openai_config()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "training_file": training_file_id,
        "model": model or settings.openai_finetune_base_model,
    }
    if suffix:
        body["suffix"] = suffix

    with httpx.Client(timeout=90.0) as client:
        response = client.post(
            f"{api_base}/fine_tuning/jobs",
            headers=headers,
            json=body,
        )
        response.raise_for_status()
        return response.json()


def get_finetune_job(job_id: str) -> dict:
    api_key, api_base = _require_openai_config()
    headers = {"Authorization": f"Bearer {api_key}"}
    with httpx.Client(timeout=45.0) as client:
        response = client.get(f"{api_base}/fine_tuning/jobs/{job_id}", headers=headers)
        response.raise_for_status()
        return response.json()


def run_export_upload_create(
    *,
    output: Path,
    limit: int | None,
    min_examples: int,
    include_synthetic: bool,
    synthetic_variants: int,
    model: str | None,
    suffix: str | None,
) -> dict:
    count = export_training_file(
        output,
        limit=limit,
        min_examples=min_examples,
        include_synthetic=include_synthetic,
        synthetic_variants=synthetic_variants,
    )
    file_id = upload_training_file(output)
    job = create_finetune_job(file_id, model=model, suffix=suffix)
    return {"example_count": count, "training_file_id": file_id, "job": job}


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenAI fine-tune helper for Market Pathways")
    sub = parser.add_subparsers(dest="command", required=True)

    export_cmd = sub.add_parser("export", help="Export labeled proof reviews to JSONL")
    export_cmd.add_argument("--output", default="training/proof_verifier.jsonl")
    export_cmd.add_argument("--limit", type=int, default=None)
    export_cmd.add_argument("--min-examples", type=int, default=25)
    export_cmd.add_argument("--include-synthetic", action="store_true")
    export_cmd.add_argument("--synthetic-variants", type=int, default=4)

    upload_cmd = sub.add_parser("upload", help="Upload a JSONL training file to OpenAI")
    upload_cmd.add_argument("--file", required=True)

    create_cmd = sub.add_parser("create-job", help="Create a fine-tune job")
    create_cmd.add_argument("--training-file-id", required=True)
    create_cmd.add_argument("--model", default=None)
    create_cmd.add_argument("--suffix", default=None)

    status_cmd = sub.add_parser("status", help="Check fine-tune job status")
    status_cmd.add_argument("--job-id", required=True)

    run_cmd = sub.add_parser("run", help="Export + upload + create job in one command")
    run_cmd.add_argument("--output", default="training/proof_verifier.jsonl")
    run_cmd.add_argument("--limit", type=int, default=None)
    run_cmd.add_argument("--min-examples", type=int, default=25)
    run_cmd.add_argument("--include-synthetic", action="store_true")
    run_cmd.add_argument("--synthetic-variants", type=int, default=4)
    run_cmd.add_argument("--model", default=None)
    run_cmd.add_argument("--suffix", default=None)

    args = parser.parse_args()

    if args.command == "export":
        count = export_training_file(
            Path(args.output),
            limit=args.limit,
            min_examples=args.min_examples,
            include_synthetic=args.include_synthetic,
            synthetic_variants=args.synthetic_variants,
        )
        print(json.dumps({"output": args.output, "examples": count}, indent=2))
        return 0

    if args.command == "upload":
        file_id = upload_training_file(Path(args.file))
        print(json.dumps({"training_file_id": file_id}, indent=2))
        return 0

    if args.command == "create-job":
        job = create_finetune_job(
            args.training_file_id,
            model=args.model,
            suffix=args.suffix,
        )
        print(json.dumps(job, indent=2))
        return 0

    if args.command == "status":
        job = get_finetune_job(args.job_id)
        print(json.dumps(job, indent=2))
        return 0

    if args.command == "run":
        result = run_export_upload_create(
            output=Path(args.output),
            limit=args.limit,
            min_examples=args.min_examples,
            include_synthetic=args.include_synthetic,
            synthetic_variants=args.synthetic_variants,
            model=args.model,
            suffix=args.suffix,
        )
        print(json.dumps(result, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
