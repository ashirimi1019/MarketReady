"""Sentinel Market Guard — monitors market shifts and creates actionable alerts."""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user_id
from app.core.config import settings
from app.models.entities import StudentNotification, MarketSignal, StudentProfile, UserPathway

ADZUNA_BASE = "https://api.adzuna.com/v1/api/jobs"
SENTINEL_ROLE_QUERIES = [
    "software engineer",
    "data analyst",
    "cybersecurity analyst",
    "frontend developer",
    "backend developer",
    "machine learning engineer",
]

router = APIRouter(prefix="/sentinel")


def _fetch_adzuna_count(query: str, country: str = "us") -> int | None:
    if not settings.adzuna_app_id or not settings.adzuna_app_key:
        return None
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"{ADZUNA_BASE}/{country}/search/1",
                params={
                    "app_id": settings.adzuna_app_id,
                    "app_key": settings.adzuna_app_key,
                    "what": query,
                    "results_per_page": 1,
                },
            )
            if resp.status_code == 200:
                return int(resp.json().get("count", 0))
    except Exception:
        pass
    return None


def _get_previous_signal_count(db: Session, role: str) -> int | None:
    """Get the most recent market signal count for a role."""
    signal = (
        db.query(MarketSignal)
        .filter(MarketSignal.role_family == role)
        .order_by(MarketSignal.window_end.desc())
        .first()
    )
    if signal and signal.source_count:
        return signal.source_count
    return None


def _create_notification(db: Session, user_id: str, kind: str, message: str, metadata: dict) -> StudentNotification:
    note = StudentNotification(
        user_id=user_id,
        kind=kind,
        message=message,
        is_read=False,
        metadata_json=metadata,
        created_at=datetime.utcnow(),
    )
    db.add(note)
    return note


def _get_user_pathway_role(db: Session, user_id: str) -> str:
    """Infer the user's target role from their pathway."""
    pathway = db.query(UserPathway).filter(UserPathway.user_id == user_id).one_or_none()
    if not pathway:
        return "software engineer"
    # Use pathway name to guess role
    from app.models.entities import CareerPathway
    cp = db.query(CareerPathway).filter(CareerPathway.id == pathway.pathway_id).first()
    if cp:
        name = (cp.name or "").lower()
        if "data" in name:
            return "data analyst"
        if "security" in name or "cyber" in name:
            return "cybersecurity analyst"
        if "frontend" in name or "web" in name:
            return "frontend developer"
        if "backend" in name:
            return "backend developer"
        if "ml" in name or "machine" in name:
            return "machine learning engineer"
    return "software engineer"


@router.post("/run")
def run_sentinel_check(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Run a Sentinel market check for the current user and generate alerts."""
    alerts_created: list[dict] = []
    role = _get_user_pathway_role(db, user_id)

    # Check for significant market demand shifts
    current_count = _fetch_adzuna_count(role)
    previous_count = _get_previous_signal_count(db, role)

    notifications_to_add = []

    if current_count is not None:
        if previous_count is not None and previous_count > 0:
            change_pct = ((current_count - previous_count) / previous_count) * 100
            if change_pct >= 20:
                msg = f"Market demand for '{role}' has increased by {change_pct:.0f}%. {current_count:,} jobs available — great time to apply!"
                note = _create_notification(db, user_id, "market_shift", msg, {
                    "role": role,
                    "current_count": current_count,
                    "previous_count": previous_count,
                    "change_pct": round(change_pct, 1),
                    "action": "Apply now",
                    "severity": "positive",
                })
                notifications_to_add.append(note)
                alerts_created.append({"kind": "market_shift", "message": msg, "severity": "positive"})
            elif change_pct <= -20:
                msg = f"Market demand for '{role}' has dropped by {abs(change_pct):.0f}%. Consider diversifying your skills or exploring adjacent roles."
                note = _create_notification(db, user_id, "market_shift", msg, {
                    "role": role,
                    "current_count": current_count,
                    "previous_count": previous_count,
                    "change_pct": round(change_pct, 1),
                    "action": "Review adjacent roles",
                    "severity": "warning",
                })
                notifications_to_add.append(note)
                alerts_created.append({"kind": "market_shift", "message": msg, "severity": "warning"})
        else:
            # First-time check — create a baseline notification
            if current_count > 1000:
                msg = f"Market pulse: {current_count:,} open positions for '{role}' — strong demand in your target lane!"
                note = _create_notification(db, user_id, "market_pulse", msg, {
                    "role": role,
                    "count": current_count,
                    "action": "Keep building",
                    "severity": "info",
                })
                notifications_to_add.append(note)
                alerts_created.append({"kind": "market_pulse", "message": msg, "severity": "info"})

    # Check profile completeness
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).one_or_none()
    if profile and not profile.github_username:
        msg = "Add your GitHub username to unlock Engineering Signal scoring and boost your MRI by up to 20 points"
        note = _create_notification(db, user_id, "profile_tip", msg, {
            "action": "Add GitHub",
            "link": "/student/profile",
            "severity": "info",
        })
        notifications_to_add.append(note)
        alerts_created.append({"kind": "profile_tip", "message": msg, "severity": "info"})

    # Add high-demand skills notification
    HIGH_DEMAND_SKILLS = ["AI/ML", "Cloud (AWS/GCP/Azure)", "Cybersecurity", "TypeScript", "Rust"]
    msg = f"2026 market signals: Highest demand for {', '.join(HIGH_DEMAND_SKILLS[:3])}. Update your plan to target these skills."
    note = _create_notification(db, user_id, "skills_trend", msg, {
        "skills": HIGH_DEMAND_SKILLS,
        "action": "Update Kanban",
        "severity": "info",
    })
    notifications_to_add.append(note)
    alerts_created.append({"kind": "skills_trend", "message": msg, "severity": "info"})

    for note in notifications_to_add:
        db.add(note)
    db.commit()

    return {
        "alerts_created": len(alerts_created),
        "alerts": alerts_created,
        "role_monitored": role,
        "market_count": current_count,
    }
