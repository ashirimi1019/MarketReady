from typing import Iterable
from datetime import datetime

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
