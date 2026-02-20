from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.entities import (
    CareerPathway,
    MarketRawIngestion,
    MarketSignal,
    MarketUpdateProposal,
    Skill,
)
from app.services.ai import (
    ai_is_configured,
    generate_market_proposal_from_signals,
    get_active_ai_model,
)
from app.services.market_connectors import fetch_external_signals
from app.services.market_intel import (
    propose_checklist_update,
    record_raw_ingestion,
    record_signals,
    run_rules_engine_from_signals,
)

logger = logging.getLogger(__name__)

_RUN_LOCK = threading.Lock()
_scheduler_task: asyncio.Task | None = None
_scheduler_stop_event: asyncio.Event | None = None
_last_scheduler_error: str | None = None


def _csv_values(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [value.strip() for value in raw.split(",") if value.strip()]


def _configured_provider(provider: str) -> bool:
    name = provider.strip().lower()
    if name == "adzuna":
        return bool(settings.adzuna_app_id and settings.adzuna_app_key)
    if name == "onet":
        return bool(settings.onet_username or settings.onet_password)
    if name == "careeronestop":
        return bool(settings.careeronestop_api_key and settings.careeronestop_user_id)
    return False


def _requested_providers() -> list[str]:
    requested = _csv_values(settings.market_auto_provider_list)
    if requested:
        return [provider.lower() for provider in requested]
    return ["adzuna", "onet", "careeronestop"]


def _enabled_providers() -> tuple[list[str], list[str]]:
    requested = _requested_providers()
    enabled = [provider for provider in requested if _configured_provider(provider)]
    disabled = [provider for provider in requested if provider not in enabled]
    return enabled, disabled


def _role_queries(pathway_name: str) -> list[str]:
    configured = _csv_values(settings.market_auto_role_families)
    if configured:
        return configured
    return [pathway_name]


def _pathway_filter_ids() -> tuple[list[UUID], list[str]]:
    raw_ids = _csv_values(settings.market_auto_pathway_ids)
    parsed: list[UUID] = []
    invalid: list[str] = []
    for raw in raw_ids:
        try:
            parsed.append(UUID(raw))
        except ValueError:
            invalid.append(raw)
    return parsed, invalid


def _serialize_signal(signal: MarketSignal, skill_name: str | None) -> dict:
    return {
        "id": str(signal.id),
        "pathway_id": str(signal.pathway_id) if signal.pathway_id else None,
        "skill_id": str(signal.skill_id) if signal.skill_id else None,
        "skill_name": skill_name,
        "role_family": signal.role_family,
        "window_start": signal.window_start.isoformat() if signal.window_start else None,
        "window_end": signal.window_end.isoformat() if signal.window_end else None,
        "frequency": signal.frequency,
        "source_count": signal.source_count,
        "metadata": signal.metadata_json,
    }


def _build_proposal(
    db: Session,
    *,
    pathway_id: UUID,
    signal_payloads: list[dict],
) -> MarketUpdateProposal:
    if ai_is_configured():
        generated = generate_market_proposal_from_signals(
            signals=signal_payloads,
            instruction="Automated pipeline proposal from live market provider signals.",
        )
        summary = generated.get("summary")
        diff = generated.get("diff") if isinstance(generated.get("diff"), dict) else {"signals": signal_payloads}
        diff.setdefault(
            "automation",
            {
                "model": get_active_ai_model(),
                "signal_count": len(signal_payloads),
                "generated_at": datetime.utcnow().isoformat(),
                "uncertainty": generated.get("uncertainty"),
            },
        )
        return propose_checklist_update(
            db,
            pathway_id=pathway_id,
            summary=summary,
            diff=diff,
        )
    return run_rules_engine_from_signals(db, pathway_id=pathway_id, signals=signal_payloads)


def run_market_automation_cycle(
    db: Session,
    *,
    dry_run: bool = False,
    trigger: str = "manual",
) -> dict:
    if not _RUN_LOCK.acquire(blocking=False):
        raise RuntimeError("Market automation is already running")
    try:
        started_at = datetime.utcnow()
        summary: dict = {
            "ok": True,
            "trigger": trigger,
            "dry_run": dry_run,
            "started_at": started_at,
            "finished_at": started_at,
            "duration_seconds": 0.0,
            "providers_requested": _requested_providers(),
            "providers_used": [],
            "pathways_considered": 0,
            "ingestions": 0,
            "signals_created": 0,
            "proposals_created": 0,
            "proposals_skipped": 0,
            "warnings": [],
            "errors": [],
        }

        providers, disabled = _enabled_providers()
        summary["providers_used"] = providers
        if disabled:
            summary["warnings"].append(
                f"Skipped unconfigured providers: {', '.join(disabled)}"
            )
        if not providers:
            summary["ok"] = False
            summary["errors"].append("No configured market providers available")
            return summary

        pathway_filter_ids, invalid_ids = _pathway_filter_ids()
        if invalid_ids:
            summary["warnings"].append(
                f"Ignored invalid pathway IDs in MARKET_AUTO_PATHWAY_IDS: {', '.join(invalid_ids)}"
            )
        pathway_query = db.query(CareerPathway).filter(CareerPathway.is_active.is_(True))
        if pathway_filter_ids:
            pathway_query = pathway_query.filter(CareerPathway.id.in_(pathway_filter_ids))
        pathways = pathway_query.order_by(CareerPathway.name.asc()).all()
        summary["pathways_considered"] = len(pathways)

        if not pathways:
            summary["warnings"].append("No active pathways found for automation run")
            return summary

        for pathway in pathways:
            pathway_id = str(pathway.id)
            for role_query in _role_queries(pathway.name):
                query_text = role_query.strip()
                if not query_text:
                    continue
                for provider in providers:
                    try:
                        signals = fetch_external_signals(
                            provider=provider,
                            query=query_text,
                            limit=settings.market_auto_signal_limit,
                            pathway_id=pathway_id,
                            role_family=role_query,
                        )
                    except Exception as exc:  # pragma: no cover - network/provider variability
                        summary["errors"].append(
                            f"{provider}:{pathway.name}:{role_query} -> {exc}"
                        )
                        continue
                    if not signals:
                        continue
                    if dry_run:
                        summary["ingestions"] += 1
                        summary["signals_created"] += len(signals)
                        continue
                    record_raw_ingestion(
                        db,
                        source=f"auto:{provider}",
                        metadata={
                            "trigger": trigger,
                            "query": query_text,
                            "role_family": role_query,
                            "pathway_id": pathway_id,
                            "signal_rows": len(signals),
                        },
                    )
                    created = record_signals(db, signals)
                    summary["ingestions"] += 1
                    summary["signals_created"] += created

        proposal_cutoff = datetime.utcnow() - timedelta(
            days=max(1, settings.market_auto_proposal_lookback_days)
        )
        cooldown_cutoff = datetime.utcnow() - timedelta(
            hours=max(1, settings.market_auto_proposal_cooldown_hours)
        )
        min_signals = max(1, settings.market_auto_proposal_min_signals)

        for pathway in pathways:
            latest = (
                db.query(MarketUpdateProposal)
                .filter(MarketUpdateProposal.pathway_id == pathway.id)
                .order_by(MarketUpdateProposal.created_at.desc())
                .first()
            )
            if latest and latest.created_at and latest.created_at >= cooldown_cutoff:
                summary["proposals_skipped"] += 1
                continue

            rows = (
                db.query(MarketSignal, Skill)
                .outerjoin(Skill, MarketSignal.skill_id == Skill.id)
                .filter(MarketSignal.pathway_id == pathway.id)
                .filter(
                    or_(
                        MarketSignal.window_end.is_(None),
                        MarketSignal.window_end >= proposal_cutoff,
                    )
                )
                .order_by(MarketSignal.window_end.desc().nullslast(), MarketSignal.id.desc())
                .limit(75)
                .all()
            )
            if len(rows) < min_signals:
                summary["proposals_skipped"] += 1
                continue

            signal_payloads = [
                _serialize_signal(signal, getattr(skill, "name", None))
                for signal, skill in rows
            ]
            if dry_run:
                summary["proposals_created"] += 1
                continue
            _build_proposal(db, pathway_id=pathway.id, signal_payloads=signal_payloads)
            summary["proposals_created"] += 1

        finished_at = datetime.utcnow()
        summary["finished_at"] = finished_at
        summary["duration_seconds"] = round((finished_at - started_at).total_seconds(), 3)

        if not dry_run:
            # Keep a compact run-level audit trail for status and troubleshooting.
            record_raw_ingestion(
                db,
                source="auto:market-cycle",
                metadata={
                    "trigger": trigger,
                    "providers_used": summary["providers_used"],
                    "pathways_considered": summary["pathways_considered"],
                    "ingestions": summary["ingestions"],
                    "signals_created": summary["signals_created"],
                    "proposals_created": summary["proposals_created"],
                    "proposals_skipped": summary["proposals_skipped"],
                    "errors": summary["errors"][:20],
                    "warnings": summary["warnings"][:20],
                    "duration_seconds": summary["duration_seconds"],
                },
            )
        return summary
    finally:
        _RUN_LOCK.release()


def market_automation_status(db: Session) -> dict:
    providers_available, providers_missing = _enabled_providers()
    pathway_ids, invalid_pathway_ids = _pathway_filter_ids()
    last_cycle = (
        db.query(MarketRawIngestion)
        .filter(MarketRawIngestion.source == "auto:market-cycle")
        .order_by(MarketRawIngestion.fetched_at.desc())
        .first()
    )
    return {
        "enabled": settings.market_auto_enabled,
        "scheduler_running": bool(_scheduler_task and not _scheduler_task.done()),
        "interval_minutes": settings.market_auto_interval_minutes,
        "providers_requested": _requested_providers(),
        "providers_available": providers_available,
        "providers_missing": providers_missing,
        "role_families": _csv_values(settings.market_auto_role_families),
        "pathway_filters": [str(pathway_id) for pathway_id in pathway_ids],
        "invalid_pathway_filters": invalid_pathway_ids,
        "last_cycle_at": last_cycle.fetched_at if last_cycle else None,
        "last_cycle_metadata": last_cycle.metadata_json if last_cycle else None,
        "last_scheduler_error": _last_scheduler_error,
    }


def _run_with_fresh_session(*, trigger: str) -> dict:
    db = SessionLocal()
    try:
        return run_market_automation_cycle(db, dry_run=False, trigger=trigger)
    finally:
        db.close()


async def _scheduler_loop(stop_event: asyncio.Event) -> None:
    global _last_scheduler_error
    if settings.market_auto_run_on_startup:
        try:
            await asyncio.to_thread(_run_with_fresh_session, trigger="startup")
        except Exception as exc:  # pragma: no cover - defensive for startup/runtime environments
            _last_scheduler_error = str(exc)
            logger.exception("Market automation startup run failed: %s", exc)

    interval_seconds = max(5, settings.market_auto_interval_minutes) * 60
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            break
        except asyncio.TimeoutError:
            pass
        try:
            await asyncio.to_thread(_run_with_fresh_session, trigger="schedule")
            _last_scheduler_error = None
        except Exception as exc:  # pragma: no cover - defensive for runtime environments
            _last_scheduler_error = str(exc)
            logger.exception("Scheduled market automation run failed: %s", exc)


async def start_market_scheduler() -> None:
    global _scheduler_task, _scheduler_stop_event
    if not settings.market_auto_enabled:
        return
    if _scheduler_task and not _scheduler_task.done():
        return
    _scheduler_stop_event = asyncio.Event()
    _scheduler_task = asyncio.create_task(
        _scheduler_loop(_scheduler_stop_event),
        name="market-automation-scheduler",
    )
    logger.info(
        "Market automation scheduler started (interval=%s minutes)",
        settings.market_auto_interval_minutes,
    )


async def stop_market_scheduler() -> None:
    global _scheduler_task, _scheduler_stop_event
    if not _scheduler_task:
        return
    if _scheduler_stop_event:
        _scheduler_stop_event.set()
    try:
        await asyncio.wait_for(_scheduler_task, timeout=5)
    except asyncio.TimeoutError:
        _scheduler_task.cancel()
    except Exception:
        logger.exception("Error while stopping market automation scheduler")
    finally:
        _scheduler_task = None
        _scheduler_stop_event = None
