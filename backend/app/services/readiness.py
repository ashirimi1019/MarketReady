from typing import Iterable
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.entities import StudentProfile, UserPathway
from app.services.engineering_signal import compute_engineering_signal
from app.services.market_alignment import compute_market_alignment

RECENCY_WINDOW_DAYS = 180
RECENCY_MAX_BONUS = 0.1
DEPLOYMENT_BONUS = 0.1


def _recency_bonus(proofs: Iterable) -> float:
    valid = [p for p in proofs if getattr(p, "status", None) == "verified"]
    if not valid:
        return 0.0

    most_recent = max((p.created_at for p in valid if p.created_at), default=None)
    if not most_recent:
        return 0.0

    now = datetime.utcnow()
    days = (now - most_recent).days
    if days <= 0:
        return RECENCY_MAX_BONUS
    if days >= RECENCY_WINDOW_DAYS:
        return 0.0

    return round(RECENCY_MAX_BONUS * (1 - (days / RECENCY_WINDOW_DAYS)), 3)


def calculate_readiness(items: Iterable, proofs: Iterable) -> dict:
    completed_item_ids = {
        p.checklist_item_id
        for p in proofs
        if getattr(p, "status", None) == "verified"
    }
    non_negotiables = [i for i in items if i.tier == "non_negotiable"]
    strong_signals = [i for i in items if i.tier == "strong_signal"]

    completed_n = sum(1 for i in non_negotiables if i.id in completed_item_ids)
    completed_s = sum(1 for i in strong_signals if i.id in completed_item_ids)

    n = max(len(non_negotiables), 1)
    s = max(len(strong_signals), 1)

    recency_bonus = _recency_bonus(proofs)
    deployment_bonus = DEPLOYMENT_BONUS if any(
        getattr(p, "proof_type", None) == "deployed_url" for p in proofs
    ) else 0.0

    base = 0.6 * (completed_n / n) + 0.3 * (completed_s / s) + recency_bonus + deployment_bonus

    capped = False
    cap_reason = None
    if any(i.is_critical and i.id not in completed_item_ids for i in non_negotiables):
        base = min(base, 0.75)
        capped = True
        missing_critical = [
            i.title for i in non_negotiables if i.is_critical and i.id not in completed_item_ids
        ]
        cap_reason = "Missing critical non-negotiable(s): " + ", ".join(missing_critical)

    base = min(max(base, 0.0), 1.0)

    if base >= 0.85:
        band = "Market Ready"
    elif base >= 0.65:
        band = "Competitive but risky"
    else:
        band = "Focus gaps"

    missing_non_negotiables = [i for i in non_negotiables if i.id not in completed_item_ids]
    missing_strong_signals = [i for i in strong_signals if i.id not in completed_item_ids]
    ordered_gaps = (missing_non_negotiables + missing_strong_signals)[:5]
    top_gaps = [i.title for i in ordered_gaps]
    next_actions = [f"Complete requirement: {i.title}" for i in ordered_gaps[:3]]

    return {
        "score": round(base * 100, 1),
        "band": band,
        "capped": capped,
        "cap_reason": cap_reason,
        "top_gaps": top_gaps,
        "next_actions": next_actions,
    }


def _band_from_score(score: float) -> str:
    if score >= 85.0:
        return "Market Ready"
    if score >= 65.0:
        return "Competitive but risky"
    return "Focus gaps"


def _has_unmet_critical_non_negotiable(items: Iterable, proofs: Iterable) -> bool:
    completed_item_ids = {
        p.checklist_item_id
        for p in proofs
        if getattr(p, "status", None) == "verified"
    }
    non_negotiables = [i for i in items if i.tier == "non_negotiable"]
    return any(i.is_critical and i.id not in completed_item_ids for i in non_negotiables)


def _verified_skill_ids(items: Iterable, proofs: Iterable) -> set[str]:
    completed_item_ids = {
        p.checklist_item_id
        for p in proofs
        if getattr(p, "status", None) == "verified"
    }
    skill_ids: set[str] = set()
    for item in items:
        if item.id in completed_item_ids and getattr(item, "skill_id", None):
            skill_ids.add(str(item.skill_id))
    return skill_ids


def _alignment_from_cached_snapshot(snapshot: dict, verified_skill_ids: set[str]) -> dict:
    high_demand_ids = list(snapshot.get("high_demand_skill_ids") or [])
    high_demand_set = set(high_demand_ids)
    if not high_demand_set:
        return {
            "score": 0.0,
            "coverage_ratio": 0.0,
            "top_demand_skills": snapshot.get("top_demand_skills") or [],
            "high_demand_skill_ids": [],
        }
    matched = len(high_demand_set.intersection(verified_skill_ids))
    coverage_ratio = matched / len(high_demand_set)
    return {
        "score": round(coverage_ratio * 100, 1),
        "coverage_ratio": round(coverage_ratio, 3),
        "top_demand_skills": snapshot.get("top_demand_skills") or [],
        "high_demand_skill_ids": high_demand_ids,
    }


def calculate_unified_readiness(
    db: Session,
    selection: UserPathway,
    items: Iterable,
    proofs: Iterable,
    *,
    profile: StudentProfile | None = None,
    engineering_cache: dict[str, dict] | None = None,
    market_alignment_cache: dict[str, dict] | None = None,
) -> dict:
    items = list(items)
    proofs = list(proofs)
    checklist = calculate_readiness(items, proofs)
    checklist_score = float(checklist.get("score", 0.0))

    if profile is None:
        profile = (
            db.query(StudentProfile)
            .filter(StudentProfile.user_id == selection.user_id)
            .one_or_none()
        )

    github_username = (
        str(getattr(profile, "github_username", "") or "").strip().lower()
        if profile
        else ""
    )
    engineering_payload = {"score": 0.0, "metrics": {}}
    if github_username:
        if engineering_cache is not None and github_username in engineering_cache:
            engineering_payload = engineering_cache[github_username]
        else:
            engineering_payload = compute_engineering_signal(github_username)
            if engineering_cache is not None:
                engineering_cache[github_username] = engineering_payload
    engineering_score = float(engineering_payload.get("score", 0.0))

    verified_skill_ids = _verified_skill_ids(items, proofs)
    pathway_key = str(selection.pathway_id)
    if market_alignment_cache is not None and pathway_key in market_alignment_cache:
        alignment_payload = _alignment_from_cached_snapshot(
            market_alignment_cache[pathway_key],
            verified_skill_ids,
        )
    else:
        alignment_payload = compute_market_alignment(
            db,
            selection.pathway_id,
            verified_skill_ids,
        )
        if market_alignment_cache is not None:
            market_alignment_cache[pathway_key] = {
                "high_demand_skill_ids": list(alignment_payload.get("high_demand_skill_ids") or []),
                "top_demand_skills": list(alignment_payload.get("top_demand_skills") or []),
            }
    alignment_score = float(alignment_payload.get("score", 0.0))

    final_score = 0.65 * checklist_score + 0.20 * engineering_score + 0.15 * alignment_score
    capped = bool(checklist.get("capped"))
    cap_reason = checklist.get("cap_reason")
    if _has_unmet_critical_non_negotiable(items, proofs):
        final_score = min(final_score, 85.0)
        capped = True
        if cap_reason:
            if "Final score capped at 85" not in cap_reason:
                cap_reason = f"{cap_reason}. Final score capped at 85 due to unmet critical requirement(s)."
        else:
            cap_reason = "Final score capped at 85 due to unmet critical requirement(s)."

    final_score = round(min(max(final_score, 0.0), 100.0), 1)
    band = _band_from_score(final_score)

    next_actions = list(checklist.get("next_actions") or [])
    if not github_username:
        next_actions.append("Add your GitHub username in Profile to unlock engineering signal scoring.")
    elif engineering_score < 55:
        next_actions.append("Strengthen GitHub signal: ship recent repos, improve README quality, and showcase impact.")

    top_demand_skills = list(alignment_payload.get("top_demand_skills") or [])
    if alignment_score < 60 and top_demand_skills:
        skill_names = [row.get("skill_name") for row in top_demand_skills if isinstance(row, dict) and row.get("skill_name")]
        if skill_names:
            next_actions.append(f"Close market demand gaps in: {', '.join(skill_names[:3])}.")
    deduped_actions = []
    for action in next_actions:
        if action and action not in deduped_actions:
            deduped_actions.append(action)

    result = {
        **checklist,
        "score": final_score,
        "checklist_score": round(checklist_score, 1),
        "engineering_score": round(engineering_score, 1),
        "market_alignment_score": round(alignment_score, 1),
        "band": band,
        "next_actions": deduped_actions[:4],
        "top_demand_skills": top_demand_skills,
        "engineering_metrics": engineering_payload.get("metrics") or {},
    }
    if capped:
        result["capped"] = True
        result["cap_reason"] = cap_reason
    return result
