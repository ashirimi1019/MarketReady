"""MRI (Market-Ready Index) endpoint — weighted formula: 0.40 * Federal Standards + 0.30 * Market Demand + 0.30 * Evidence Density"""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user_id
from app.models.entities import (
    ChecklistItem, ChecklistVersion, Proof, UserPathway, StudentProfile,
)

MRI_WEIGHTS = {"federal_standards": 0.40, "market_demand": 0.30, "evidence_density": 0.30}

router = APIRouter(prefix="/score")


def _get_user_pathway_and_profile(db: Session, user_id: str):
    selection = db.query(UserPathway).filter(UserPathway.user_id == user_id).one_or_none()
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).one_or_none()
    return selection, profile


def _get_checklist_items(db: Session, selection: UserPathway) -> list[ChecklistItem]:
    version_id = selection.checklist_version_id
    if not version_id:
        version = (
            db.query(ChecklistVersion)
            .filter(ChecklistVersion.pathway_id == selection.pathway_id)
            .filter(ChecklistVersion.status == "published")
            .order_by(ChecklistVersion.version_number.desc())
            .first()
        )
        if not version:
            return []
        version_id = version.id
    return db.query(ChecklistItem).filter(ChecklistItem.version_id == version_id).all()


def compute_mri_components(db: Session, user_id: str) -> dict[str, Any]:
    """Compute MRI score with three components."""
    selection, profile = _get_user_pathway_and_profile(db, user_id)
    if not selection:
        return {
            "score": 0.0,
            "components": {"federal_standards": 0.0, "market_demand": 0.0, "evidence_density": 0.0},
            "weights": MRI_WEIGHTS,
            "gaps": [],
            "recommendations": ["Complete your pathway setup to get your MRI score"],
            "band": "Not Started",
            "formula": "MRI = (Federal Standards × 0.40) + (Market Demand × 0.30) + (Evidence Density × 0.30)",
        }

    items = _get_checklist_items(db, selection)
    proofs = db.query(Proof).filter(Proof.user_id == user_id).all()

    verified_ids = {str(p.checklist_item_id) for p in proofs if p.status == "verified"}
    all_item_ids = {str(i.id) for i in items}
    non_negotiables = [i for i in items if i.tier == "non_negotiable"]
    strong_signals = [i for i in items if i.tier == "strong_signal"]

    # Federal Standards Score: based on non-negotiable + strong_signal completion (O*NET weight)
    n_total = max(len(non_negotiables), 1)
    s_total = max(len(strong_signals), 1)
    n_done = sum(1 for i in non_negotiables if str(i.id) in verified_ids)
    s_done = sum(1 for i in strong_signals if str(i.id) in verified_ids)
    federal_score = min(100.0, round((0.7 * (n_done / n_total) + 0.3 * (s_done / s_total)) * 100, 1))

    # Market Demand Score: ratio of verified skills to all checklist items (proxy for Adzuna signal)
    total_items = max(len(items), 1)
    total_verified = len(verified_ids.intersection(all_item_ids))
    market_score = min(100.0, round((total_verified / total_items) * 100, 1))

    # Evidence Density Score: diversity of proof types and recency
    proof_types = {p.proof_type for p in proofs if p.status == "verified"}
    type_diversity = min(len(proof_types), 5) / 5
    recent_proofs = [
        p for p in proofs
        if p.status == "verified" and p.created_at
    ]
    recency_score = 1.0 if recent_proofs else 0.0
    github_bonus = 0.2 if (profile and profile.github_username) else 0.0
    evidence_score = min(100.0, round((type_diversity * 0.6 + recency_score * 0.2 + github_bonus) * 100, 1))

    mri_score = round(
        MRI_WEIGHTS["federal_standards"] * federal_score +
        MRI_WEIGHTS["market_demand"] * market_score +
        MRI_WEIGHTS["evidence_density"] * evidence_score,
        1,
    )

    # Top gaps
    missing_items = [i for i in items if str(i.id) not in verified_ids]
    missing_items.sort(key=lambda i: (0 if i.tier == "non_negotiable" else 1 if i.tier == "strong_signal" else 2))
    gaps = [i.title for i in missing_items[:5]]

    # Actionable recommendations
    recommendations = []
    if federal_score < 60:
        recommendations.append("Complete more non-negotiable checklist requirements to boost your Federal Standards score")
    if market_score < 50:
        recommendations.append("Add more verified proofs to improve your Market Demand alignment")
    if evidence_score < 50:
        recommendations.append("Diversify your proof types (certifications, projects, deployments) to increase Evidence Density")
    if not (profile and profile.github_username):
        recommendations.append("Add your GitHub username to unlock Engineering Signal scoring")
    if not recommendations:
        recommendations.append("You're performing well! Keep adding proofs to maintain your edge")

    if mri_score >= 85:
        band = "Market Ready"
    elif mri_score >= 65:
        band = "Competitive"
    elif mri_score >= 45:
        band = "Developing"
    else:
        band = "Focus Gaps"

    return {
        "score": mri_score,
        "components": {
            "federal_standards": federal_score,
            "market_demand": market_score,
            "evidence_density": evidence_score,
        },
        "weights": MRI_WEIGHTS,
        "gaps": gaps,
        "recommendations": recommendations[:4],
        "band": band,
        "formula": "MRI = (Federal Standards × 0.40) + (Market Demand × 0.30) + (Evidence Density × 0.30)",
    }


@router.get("/mri")
def get_mri_score(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get the MRI (Market-Ready Index) score with weighted component breakdown."""
    try:
        return compute_mri_components(db, user_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"MRI calculation error: {str(exc)[:200]}")
