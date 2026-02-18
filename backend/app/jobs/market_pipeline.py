from sqlalchemy.orm import Session

from app.services.market_intel import (
    record_raw_ingestion,
    record_signals,
    propose_checklist_update,
    run_rules_engine_from_signals,
)
from app.services.market_connectors import fetch_external_signals


def run_collection_job(
    db: Session,
    *,
    source: str,
    storage_key: str | None = None,
    metadata: dict | None = None,
):
    return record_raw_ingestion(db, source=source, storage_key=storage_key, metadata=metadata)


def run_extraction_job(db: Session, signals: list[dict]):
    return record_signals(db, signals)


def run_rules_engine_job(
    db: Session,
    *,
    pathway_id,
    signals: list[dict] | None = None,
    summary: str | None = None,
    diff: dict | None = None,
    proposed_version_number: int | None = None,
):
    if signals is not None:
        return run_rules_engine_from_signals(db, pathway_id, signals)
    return propose_checklist_update(
        db,
        pathway_id=pathway_id,
        summary=summary,
        diff=diff,
        proposed_version_number=proposed_version_number,
    )


def run_external_ingest_job(
    db: Session,
    *,
    provider: str,
    query: str,
    pathway_id: str | None = None,
    role_family: str | None = None,
    limit: int = 25,
):
    signals = fetch_external_signals(
        provider=provider,
        query=query,
        limit=limit,
        pathway_id=pathway_id,
        role_family=role_family,
    )
    if not signals:
        return {"provider": provider, "ingested": 0, "created_signals": 0}

    record_raw_ingestion(
        db,
        source=f"external:{provider}",
        metadata={
            "query": query,
            "pathway_id": pathway_id,
            "role_family": role_family,
            "ingested_rows": len(signals),
        },
    )
    created = record_signals(db, signals)
    return {"provider": provider, "ingested": len(signals), "created_signals": created}
