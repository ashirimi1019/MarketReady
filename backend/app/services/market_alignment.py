from __future__ import annotations

from math import ceil
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.models.entities import MarketSignal, Skill


def _to_skill_ids(values: Iterable[Any]) -> set[str]:
    ids: set[str] = set()
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            ids.add(text)
    return ids


def compute_market_alignment(db: Session, pathway_id, verified_skill_ids) -> dict[str, Any]:
    verified_set = _to_skill_ids(verified_skill_ids or [])

    signals = (
        db.query(MarketSignal)
        .filter(MarketSignal.pathway_id == pathway_id)
        .filter(MarketSignal.skill_id.isnot(None))
        .all()
    )
    if not signals:
        return {
            "score": 0.0,
            "coverage_ratio": 0.0,
            "top_demand_skills": [],
            "high_demand_skill_ids": [],
        }

    demand_by_skill: dict[str, float] = {}
    skill_db_values: dict[str, Any] = {}
    for row in signals:
        skill_id = str(row.skill_id)
        skill_db_values[skill_id] = row.skill_id
        demand_by_skill[skill_id] = demand_by_skill.get(skill_id, 0.0) + max(float(row.frequency or 0.0), 0.0)

    if not demand_by_skill:
        return {
            "score": 0.0,
            "coverage_ratio": 0.0,
            "top_demand_skills": [],
            "high_demand_skill_ids": [],
        }

    max_frequency = max(demand_by_skill.values()) if demand_by_skill else 0.0
    normalized = {
        skill_id: (freq / max_frequency if max_frequency > 0 else 0.0)
        for skill_id, freq in demand_by_skill.items()
    }
    ordered_skill_ids = sorted(
        normalized.keys(),
        key=lambda skill_id: (normalized[skill_id], demand_by_skill[skill_id], skill_id),
        reverse=True,
    )

    top_count = max(1, ceil(len(ordered_skill_ids) * 0.30))
    high_demand_skill_ids = ordered_skill_ids[:top_count]
    high_demand_set = set(high_demand_skill_ids)
    matched = len(high_demand_set.intersection(verified_set))
    coverage_ratio = matched / top_count
    alignment_score = round(coverage_ratio * 100, 1)

    db_skill_ids = [skill_db_values[skill_id] for skill_id in high_demand_skill_ids if skill_id in skill_db_values]
    skill_names = {
        str(row.id): row.name
        for row in db.query(Skill).filter(Skill.id.in_(db_skill_ids)).all()
    }
    top_demand_skills = [
        {
            "skill_id": skill_id,
            "skill_name": skill_names.get(skill_id),
            "frequency": round(demand_by_skill[skill_id], 3),
            "normalized_frequency": round(normalized[skill_id], 3),
        }
        for skill_id in high_demand_skill_ids
    ]

    return {
        "score": alignment_score,
        "coverage_ratio": round(coverage_ratio, 3),
        "top_demand_skills": top_demand_skills,
        "high_demand_skill_ids": high_demand_skill_ids,
    }
