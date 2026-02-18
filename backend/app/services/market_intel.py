from datetime import datetime
from typing import Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.entities import (
    MarketRawIngestion,
    MarketSignal,
    MarketUpdateProposal,
    Skill,
    ChecklistVersion,
)


def record_raw_ingestion(
    db: Session,
    *,
    source: str,
    storage_key: str | None = None,
    metadata: dict | None = None,
) -> MarketRawIngestion:
    entry = MarketRawIngestion(
        source=source,
        fetched_at=datetime.utcnow(),
        storage_key=storage_key,
        metadata_json=metadata,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def record_signals(db: Session, signals: Iterable[dict]) -> int:
    created = 0
    for signal in signals:
        skill_id = signal.get("skill_id")
        skill_name = signal.get("skill_name")
        if not skill_id and skill_name:
            skill = db.query(Skill).filter(Skill.name == skill_name).one_or_none()
            if not skill:
                skill = Skill(name=skill_name)
                db.add(skill)
                db.flush()
            skill_id = skill.id

        db.add(
            MarketSignal(
                pathway_id=signal.get("pathway_id"),
                skill_id=skill_id,
                role_family=signal.get("role_family"),
                window_start=signal.get("window_start"),
                window_end=signal.get("window_end"),
                frequency=signal.get("frequency"),
                source_count=signal.get("source_count"),
                metadata_json=signal.get("metadata"),
            )
        )
        created += 1

    db.commit()
    return created


def propose_checklist_update(
    db: Session,
    *,
    pathway_id,
    summary: str | None = None,
    diff: dict | None = None,
    proposed_version_number: int | None = None,
) -> MarketUpdateProposal:
    if proposed_version_number is None:
        latest_version = (
            db.query(func.max(ChecklistVersion.version_number))
            .filter(ChecklistVersion.pathway_id == pathway_id)
            .scalar()
            or 0
        )
        proposed_version_number = int(latest_version) + 1

    proposal = MarketUpdateProposal(
        pathway_id=pathway_id,
        proposed_version_number=proposed_version_number,
        status="draft",
        summary=summary,
        diff=diff,
        created_at=datetime.utcnow(),
    )
    db.add(proposal)
    db.commit()
    db.refresh(proposal)
    return proposal


def run_rules_engine_from_signals(db: Session, pathway_id, signals: list[dict]) -> MarketUpdateProposal:
    summary = f"Auto-generated proposal from {len(signals)} market signals."
    diff = {"signals": signals}
    return propose_checklist_update(db, pathway_id=pathway_id, summary=summary, diff=diff)
