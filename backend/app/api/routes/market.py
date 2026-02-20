from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.schemas.api import (
    MarketIngestIn,
    MarketIngestOut,
    MarketExternalIngestIn,
    MarketExternalIngestOut,
    MarketAutomationRunIn,
    MarketAutomationOut,
    MarketAutomationStatusOut,
    MarketSignalsIn,
    MarketSignalsOut,
    MarketSignalOut,
    MarketProposalIn,
    MarketCopilotProposalIn,
    MarketProposalOut,
)
from app.models.entities import MarketSignal, MarketUpdateProposal, Skill
from app.services.ai import ai_is_configured, generate_market_proposal_from_signals, get_active_ai_model
from app.services.market_intel import (
    record_raw_ingestion,
    record_signals,
    propose_checklist_update,
)
from app.services.market_automation import (
    market_automation_status,
    run_market_automation_cycle,
)
from app.services.market_connectors import fetch_external_signals

router = APIRouter(prefix="/admin/market", dependencies=[Depends(require_admin)])


def _serialize_proposal(proposal: MarketUpdateProposal) -> dict:
    return {
        "id": proposal.id,
        "pathway_id": proposal.pathway_id,
        "proposed_version_number": proposal.proposed_version_number,
        "status": proposal.status,
        "summary": proposal.summary,
        "diff": proposal.diff,
        "created_at": proposal.created_at,
        "approved_at": proposal.approved_at,
        "approved_by": proposal.approved_by,
        "published_at": proposal.published_at,
        "published_by": proposal.published_by,
    }


@router.post("/ingestions", response_model=MarketIngestOut)
def create_ingestion(payload: MarketIngestIn, db: Session = Depends(get_db)):
    entry = record_raw_ingestion(
        db,
        source=payload.source,
        storage_key=payload.storage_key,
        metadata=payload.metadata,
    )
    return {
        "id": entry.id,
        "source": entry.source,
        "fetched_at": entry.fetched_at,
        "storage_key": entry.storage_key,
        "metadata": entry.metadata_json,
    }


@router.post("/signals", response_model=MarketSignalsOut)
def create_signals(payload: MarketSignalsIn, db: Session = Depends(get_db)):
    signal_payloads = [
        signal.model_dump() if hasattr(signal, "model_dump") else signal.dict()
        for signal in payload.signals
    ]
    created = record_signals(db, signal_payloads)
    return {"created": created}


@router.post("/ingest/external", response_model=MarketExternalIngestOut)
def ingest_external_market_data(
    payload: MarketExternalIngestIn,
    db: Session = Depends(get_db),
):
    pathway_id = str(payload.pathway_id) if payload.pathway_id else None
    try:
        signals = fetch_external_signals(
            provider=payload.provider,
            query=payload.query or payload.role_family or "software engineer",
            limit=payload.limit,
            pathway_id=pathway_id,
            role_family=payload.role_family,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not signals:
        return {"provider": payload.provider, "ingested": 0, "created_signals": 0}

    record_raw_ingestion(
        db,
        source=f"external:{payload.provider}",
        metadata={
            "query": payload.query,
            "role_family": payload.role_family,
            "pathway_id": pathway_id,
            "ingested_rows": len(signals),
        },
    )
    created = record_signals(db, signals)
    return {
        "provider": payload.provider,
        "ingested": len(signals),
        "created_signals": created,
    }


@router.get("/automation/status", response_model=MarketAutomationStatusOut)
def get_market_automation_status(db: Session = Depends(get_db)):
    return market_automation_status(db)


@router.post("/automation/run", response_model=MarketAutomationOut)
def run_market_automation(
    payload: MarketAutomationRunIn,
    db: Session = Depends(get_db),
):
    trigger = (payload.trigger or "manual").strip() or "manual"
    try:
        return run_market_automation_cycle(
            db,
            dry_run=payload.dry_run,
            trigger=trigger[:60],
        )
    except RuntimeError as exc:
        detail = str(exc)
        status_code = 409 if "already running" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc


@router.get("/signals", response_model=list[MarketSignalOut])
def list_signals(
    pathway_id: str | None = None,
    role_family: str | None = None,
    skill_name: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    query = db.query(MarketSignal, Skill).outerjoin(
        Skill, MarketSignal.skill_id == Skill.id
    )
    if pathway_id:
        query = query.filter(MarketSignal.pathway_id == pathway_id)
    if role_family:
        query = query.filter(MarketSignal.role_family == role_family)
    if skill_name:
        query = query.filter(Skill.name.ilike(f"%{skill_name}%"))

    rows = (
        query.order_by(MarketSignal.window_end.desc().nullslast(), MarketSignal.id.desc())
        .limit(limit)
        .all()
    )
    results = []
    for signal, skill in rows:
        results.append(
            {
                "id": signal.id,
                "pathway_id": signal.pathway_id,
                "skill_id": signal.skill_id,
                "skill_name": getattr(skill, "name", None),
                "role_family": signal.role_family,
                "window_start": signal.window_start,
                "window_end": signal.window_end,
                "frequency": signal.frequency,
                "source_count": signal.source_count,
                "metadata": signal.metadata_json,
            }
        )
    return results


@router.post("/proposals", response_model=MarketProposalOut)
def create_proposal(payload: MarketProposalIn, db: Session = Depends(get_db)):
    proposal = propose_checklist_update(
        db,
        pathway_id=payload.pathway_id,
        summary=payload.summary,
        diff=payload.diff,
        proposed_version_number=payload.proposed_version_number,
    )
    return _serialize_proposal(proposal)


@router.get("/proposals", response_model=list[MarketProposalOut])
def list_proposals(
    pathway_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    query = db.query(MarketUpdateProposal)
    if pathway_id:
        query = query.filter(MarketUpdateProposal.pathway_id == pathway_id)
    if status:
        query = query.filter(MarketUpdateProposal.status == status)

    proposals = query.order_by(MarketUpdateProposal.created_at.desc()).limit(limit).all()
    return [_serialize_proposal(proposal) for proposal in proposals]


@router.post("/proposals/copilot", response_model=MarketProposalOut)
def create_proposal_with_copilot(
    payload: MarketCopilotProposalIn,
    db: Session = Depends(get_db),
):
    signal_query = db.query(MarketSignal, Skill).outerjoin(
        Skill, MarketSignal.skill_id == Skill.id
    ).filter(MarketSignal.pathway_id == payload.pathway_id)
    if payload.signal_ids:
        signal_query = signal_query.filter(MarketSignal.id.in_(payload.signal_ids))

    rows = (
        signal_query.order_by(MarketSignal.window_end.desc().nullslast(), MarketSignal.id.desc())
        .limit(50)
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No market signals found for proposal generation")

    signals: list[dict] = []
    for signal, skill in rows:
        signals.append(
            {
                "id": str(signal.id),
                "pathway_id": str(signal.pathway_id) if signal.pathway_id else None,
                "skill_id": str(signal.skill_id) if signal.skill_id else None,
                "skill_name": skill.name if skill else None,
                "role_family": signal.role_family,
                "window_start": signal.window_start.isoformat() if signal.window_start else None,
                "window_end": signal.window_end.isoformat() if signal.window_end else None,
                "frequency": signal.frequency,
                "source_count": signal.source_count,
                "metadata": signal.metadata_json,
            }
        )

    generated = generate_market_proposal_from_signals(
        signals=signals,
        instruction=payload.instruction,
    )
    diff = generated.get("diff") if isinstance(generated.get("diff"), dict) else {"signals": signals}
    diff.setdefault(
        "copilot_meta",
        {
            "model": get_active_ai_model() if ai_is_configured() else "rules-based",
            "signal_count": len(signals),
            "instruction": payload.instruction,
            "uncertainty": generated.get("uncertainty"),
        },
    )
    proposal = propose_checklist_update(
        db,
        pathway_id=payload.pathway_id,
        summary=generated.get("summary"),
        diff=diff,
    )
    return _serialize_proposal(proposal)


@router.post("/proposals/{proposal_id}/approve", response_model=MarketProposalOut)
def approve_proposal(
    proposal_id: str,
    x_admin_actor: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    proposal = db.query(MarketUpdateProposal).get(proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    proposal.status = "approved"
    proposal.approved_at = datetime.utcnow()
    proposal.approved_by = (x_admin_actor or "admin").strip() or "admin"
    db.commit()
    db.refresh(proposal)
    return _serialize_proposal(proposal)


@router.post("/proposals/{proposal_id}/publish", response_model=MarketProposalOut)
def publish_proposal(
    proposal_id: str,
    x_admin_actor: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    proposal = db.query(MarketUpdateProposal).get(proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if proposal.status not in {"approved", "draft"}:
        raise HTTPException(status_code=400, detail="Proposal cannot be published in current status")
    proposal.status = "published"
    proposal.published_at = datetime.utcnow()
    proposal.published_by = (x_admin_actor or "admin").strip() or "admin"
    db.commit()
    db.refresh(proposal)
    return _serialize_proposal(proposal)
