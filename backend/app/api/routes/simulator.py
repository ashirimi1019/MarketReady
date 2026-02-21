"""2027 Future-Shock Simulator — adjusts skill values based on AI acceleration."""
from __future__ import annotations
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user_id
from app.models.entities import ChecklistItem, ChecklistVersion, Proof, UserPathway, StudentProfile

router = APIRouter(prefix="/simulator")

# Resilience multipliers by skill category
RESILIENCE_MULTIPLIERS: dict[str, float] = {
    # High resilience - AI-proof or AI-enhanced
    "system design": 1.8,
    "architecture": 1.8,
    "cybersecurity": 1.7,
    "cloud": 1.6,
    "devops": 1.6,
    "ethical ai": 1.7,
    "prompt engineering": 1.7,
    "machine learning": 1.5,
    "leadership": 1.6,
    "product management": 1.5,
    "data engineering": 1.5,
    "distributed systems": 1.7,
    "rag": 1.7,

    # Moderate resilience
    "python": 1.3,
    "typescript": 1.2,
    "react": 1.2,
    "api development": 1.3,
    "sql": 1.2,
    "testing": 1.2,
    "backend": 1.3,

    # Lower resilience - AI is replacing these
    "manual testing": 0.4,
    "basic html": 0.5,
    "basic css": 0.5,
    "data entry": 0.3,
    "documentation": 0.6,
    "basic frontend": 0.6,
    "copy writing": 0.5,
    "boilerplate code": 0.4,
}

PIVOT_RECOMMENDATIONS: dict[str, list[str]] = {
    "high": [
        "Focus on system design and architecture skills — AI can't replace strategic thinking",
        "Invest in cybersecurity: threat modeling and ethical AI governance are highly resilient",
        "Build cloud and DevOps expertise for infrastructure-level roles",
    ],
    "medium": [
        "Add AI collaboration skills to your toolkit (prompt engineering, AI-assisted development)",
        "Deepen domain expertise in your chosen pathway — vertical knowledge is resilient",
        "Focus on skills that require human judgment and creativity",
    ],
    "low": [
        "Your current skills show good AI-era resilience",
        "Consider adding cutting-edge specializations like MLOps or distributed AI systems",
        "Lead with problem-solving abilities rather than specific tool knowledge",
    ],
}


class FutureShockIn(BaseModel):
    acceleration: float = Field(default=50.0, ge=0.0, le=100.0, description="AI acceleration level 0-100")


def _normalize(text: str) -> str:
    return text.lower().strip()


def _get_multiplier(skill_name: str, acceleration: float) -> float:
    """Get skill resilience multiplier adjusted for acceleration level."""
    skill_lower = _normalize(skill_name)
    base_mult = 1.0
    for keyword, mult in RESILIENCE_MULTIPLIERS.items():
        if keyword in skill_lower:
            base_mult = mult
            break
    # Interpolate: at acceleration=0, multiplier=1.0; at acceleration=100, full effect
    accel_factor = acceleration / 100.0
    return 1.0 + (base_mult - 1.0) * accel_factor


def _classify_skill(skill_name: str, multiplier: float) -> str:
    if multiplier >= 1.4:
        return "resilient"
    if multiplier <= 0.7:
        return "at_risk"
    return "stable"


@router.post("/future-shock")
def future_shock_simulator(
    payload: FutureShockIn,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Simulate how AI acceleration impacts the user's skill portfolio."""
    acceleration = payload.acceleration

    # Get user's verified skills
    selection = db.query(UserPathway).filter(UserPathway.user_id == user_id).one_or_none()
    if not selection:
        return {
            "acceleration": acceleration,
            "adjusted_score": 0.0,
            "original_score": 0.0,
            "delta": 0.0,
            "skill_profiles": [],
            "risk_level": "unknown",
            "recommendations": ["Complete your pathway setup first"],
        }

    version_id = selection.checklist_version_id
    if not version_id:
        version = (
            db.query(ChecklistVersion)
            .filter(ChecklistVersion.pathway_id == selection.pathway_id)
            .filter(ChecklistVersion.status == "published")
            .order_by(ChecklistVersion.version_number.desc())
            .first()
        )
        if version:
            version_id = version.id

    items = db.query(ChecklistItem).filter(ChecklistItem.version_id == version_id).all() if version_id else []
    proofs = db.query(Proof).filter(Proof.user_id == user_id).all()
    verified_ids = {str(p.checklist_item_id) for p in proofs if p.status == "verified"}

    # Compute original score (simple ratio)
    total = max(len(items), 1)
    verified = sum(1 for i in items if str(i.id) in verified_ids)
    original_score = round((verified / total) * 100, 1)

    # Compute adjusted score with resilience multipliers
    weighted_total = 0.0
    weighted_verified = 0.0
    skill_profiles = []

    for item in items:
        multiplier = _get_multiplier(item.title, acceleration)
        is_verified = str(item.id) in verified_ids
        weighted_total += multiplier
        if is_verified:
            weighted_verified += multiplier

        classification = _classify_skill(item.title, multiplier)
        if classification != "stable":  # Only show notable skills
            skill_profiles.append({
                "skill": item.title,
                "multiplier": round(multiplier, 2),
                "classification": classification,
                "verified": is_verified,
            })

    adjusted_score = round((weighted_verified / weighted_total) * 100, 1) if weighted_total > 0 else 0.0
    delta = round(adjusted_score - original_score, 1)

    # Determine risk level
    at_risk_count = sum(1 for s in skill_profiles if s["classification"] == "at_risk" and s["verified"])
    resilient_count = sum(1 for s in skill_profiles if s["classification"] == "resilient" and s["verified"])

    if at_risk_count > resilient_count:
        risk_level = "high"
    elif at_risk_count > 0:
        risk_level = "medium"
    else:
        risk_level = "low"

    return {
        "acceleration": acceleration,
        "adjusted_score": adjusted_score,
        "original_score": original_score,
        "delta": delta,
        "skill_profiles": sorted(skill_profiles, key=lambda x: x["multiplier"], reverse=True)[:15],
        "risk_level": risk_level,
        "at_risk_count": at_risk_count,
        "resilient_count": resilient_count,
        "recommendations": PIVOT_RECOMMENDATIONS.get(risk_level, [])[:3],
        "formula_note": f"Score adjusted using AI resilience multipliers at {acceleration:.0f}% acceleration",
    }
