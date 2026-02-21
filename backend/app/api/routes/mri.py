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

# Proficiency multipliers: how much each level contributes to the score
PROFICIENCY_MULTIPLIERS = {
    "professional": 1.0,
    "intermediate": 0.75,
    "beginner": 0.50,
}

# For non-negotiable items, AI-verified certs get a bonus
AI_VERIFIED_BONUS = 1.15  # 15% bonus for AI-verified certificates

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
    """Compute MRI score with three components including proficiency weighting."""
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
            "proficiency_breakdown": {"beginner": 0, "intermediate": 0, "professional": 0},
            "ai_verified_certs": 0,
        }

    items = _get_checklist_items(db, selection)
    proofs = db.query(Proof).filter(Proof.user_id == user_id).all()

    # Build proof lookup by checklist_item_id → best proof
    best_proof: dict[str, Proof] = {}
    for p in proofs:
        item_key = str(p.checklist_item_id)
        if p.status == "verified":
            # AI-verified cert takes priority; otherwise keep highest proficiency
            existing = best_proof.get(item_key)
            if not existing or existing.status != "verified":
                best_proof[item_key] = p
            elif _get_prof_mult(p) > _get_prof_mult(existing):
                best_proof[item_key] = p

    non_negotiables = [i for i in items if i.tier == "non_negotiable"]
    strong_signals = [i for i in items if i.tier == "strong_signal"]
    all_item_ids = {str(i.id) for i in items}

    # ─── Federal Standards Score ───────────────────────────────
    # Weighted by proficiency. Non-negotiables need AI-verified cert for full credit.
    n_total = max(len(non_negotiables), 1)
    s_total = max(len(strong_signals), 1)

    n_weighted = sum(
        _item_credit(str(i.id), best_proof, i.tier) for i in non_negotiables
    )
    s_weighted = sum(
        _item_credit(str(i.id), best_proof, i.tier) for i in strong_signals
    )
    federal_score = min(100.0, round(
        (0.70 * (n_weighted / n_total) + 0.30 * (s_weighted / s_total)) * 100, 1
    ))

    # ─── Market Demand Score ───────────────────────────────────
    # Ratio of proficiency-weighted completions to total items
    total_items = max(len(items), 1)
    total_weighted = sum(
        _item_credit(str(i.id), best_proof, i.tier) for i in items
    )
    market_score = min(100.0, round((total_weighted / total_items) * 100, 1))

    # ─── Evidence Density Score ────────────────────────────────
    # Diversity of proof types + recency + GitHub bonus + proficiency mix
    verified_proofs = [p for p in proofs if p.status == "verified"]
    proof_types = {p.proof_type for p in verified_proofs}
    type_diversity = min(len(proof_types), 5) / 5

    # Proficiency quality score: average proficiency of verified proofs
    if verified_proofs:
        avg_prof = sum(_get_prof_mult(p) for p in verified_proofs) / len(verified_proofs)
    else:
        avg_prof = 0.0

    # AI-verified certs give bonus
    ai_cert_count = sum(
        1 for p in verified_proofs
        if p.proof_type in ("cert_upload", "certificate") or "cert" in (p.proof_type or "")
    )
    ai_cert_bonus = min(ai_cert_count * 0.05, 0.20)  # up to 20% bonus from certs

    github_bonus = 0.15 if (profile and profile.github_username) else 0.0
    evidence_score = min(100.0, round(
        (type_diversity * 0.35 + avg_prof * 0.35 + ai_cert_bonus * 0.15 + github_bonus * 0.15) * 100, 1
    ))

    mri_score = round(
        MRI_WEIGHTS["federal_standards"] * federal_score +
        MRI_WEIGHTS["market_demand"] * market_score +
        MRI_WEIGHTS["evidence_density"] * evidence_score,
        1,
    )

    # Top gaps (prioritize non-negotiables)
    missing_items = [i for i in items if str(i.id) not in best_proof]
    missing_items.sort(key=lambda i: (0 if i.tier == "non_negotiable" else 1 if i.tier == "strong_signal" else 2))
    gaps = [i.title for i in missing_items[:5]]

    # Actionable recommendations
    recommendations = []
    if federal_score < 60:
        recommendations.append("Complete non-negotiable requirements and aim for Professional proficiency to boost your Federal Standards score")
    if market_score < 50:
        recommendations.append("Add more verified proofs with higher proficiency levels to improve Market Demand alignment")
    if evidence_score < 50:
        recommendations.append("Upload AI-verified certificates for non-negotiable items — they give a 15% bonus to Evidence Density")
    if not any("cert" in (p.proof_type or "") for p in verified_proofs):
        recommendations.append("Submit at least one AI-verified certificate to unlock certificate bonuses in your MRI score")
    if not (profile and profile.github_username):
        recommendations.append("Add your GitHub username to unlock Engineering Signal scoring (+15 to Evidence Density)")
    if not recommendations:
        recommendations.append("Strong profile! Level up remaining items to Professional proficiency for maximum MRI score")

    # Proficiency breakdown
    prof_counts: dict[str, int] = {"beginner": 0, "intermediate": 0, "professional": 0}
    for p in best_proof.values():
        lvl = (p.proficiency_level or "intermediate").lower()
        if lvl in prof_counts:
            prof_counts[lvl] += 1

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
        "proficiency_breakdown": prof_counts,
        "ai_verified_certs": ai_cert_count,
    }


def _get_prof_mult(proof: Proof) -> float:
    return PROFICIENCY_MULTIPLIERS.get((proof.proficiency_level or "intermediate").lower(), 0.75)


def _item_credit(item_id: str, best_proof: dict, tier: str) -> float:
    """Credit for a checklist item: 0 if not verified, else proficiency mult × AI bonus for non-negotiables."""
    proof = best_proof.get(item_id)
    if not proof:
        return 0.0
    mult = _get_prof_mult(proof)
    # Non-negotiable AI-verified certs get a 15% bonus
    is_cert = "cert" in (proof.proof_type or "").lower()
    if tier == "non_negotiable" and is_cert:
        mult = min(mult * AI_VERIFIED_BONUS, 1.0)
    return mult


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
