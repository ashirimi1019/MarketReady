from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.services.ai import (
    _call_llm,
    _log_ai_audit,
    _safe_json,
    ai_is_configured,
    ai_strict_mode_enabled,
    get_active_ai_model,
)
from app.services.market_stress import build_user_resume_summary, compute_market_stress_test

PIVOT_THRESHOLD_DELTA = 15.0
PIVOT_ROLE_CANDIDATES = (
    "backend engineer",
    "cloud security engineer",
    "data engineer",
    "ml engineer",
)


def _call_json_agent(system_prompt: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not ai_is_configured():
        if ai_strict_mode_enabled():
            raise RuntimeError("AI strict mode: orchestrator requires configured provider.")
        return {}

    response = _call_llm(
        system_prompt=system_prompt,
        user_content=_safe_json(payload),
        expect_json=True,
        max_tokens=1200,
        temperature=0.2,
    )
    if not response:
        if ai_strict_mode_enabled():
            raise RuntimeError("AI strict mode: agent returned no response.")
        return {}

    try:
        return _safe_json(response)
    except Exception:
        if ai_strict_mode_enabled():
            raise RuntimeError("AI strict mode: agent returned invalid JSON.")
        return {}


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        out: list[str] = []
        for entry in value:
            text = str(entry).strip()
            if text:
                out.append(text)
        return out
    return []


def _default_mission(missing_skills: list[str], target_job: str, location: str) -> dict[str, list[str]]:
    top = missing_skills[:3] if missing_skills else ["core backend", "rest api", "cloud fundamentals"]
    day_0_30 = [
        f"Day 7: Build a mini project covering {top[0]} because local demand for {target_job} is market-weighted.",
        f"Day 14: Solve one SQL LeetCode medium problem because employers in {location} screen for query fluency.",
    ]
    day_31_60 = [
        f"Day 35: Add production-grade API tests for {top[1] if len(top) > 1 else 'rest api'} to increase proof quality.",
        "Day 49: Deploy and document your project with measurable outcomes.",
    ]
    day_61_90 = [
        f"Day 70: Add a cloud/security hardening step for {top[2] if len(top) > 2 else 'cloud fundamentals'}.",
        "Day 85: Publish final portfolio write-up with metrics and architecture diagram.",
    ]
    weekly_checkboxes = [
        "Ship at least one verifiable artifact this week.",
        "Link one repo and run Proof Auditor.",
        "Review market trend panel before choosing next task.",
    ]
    return {
        "day_0_30": day_0_30,
        "day_31_60": day_31_60,
        "day_61_90": day_61_90,
        "weekly_checkboxes": weekly_checkboxes,
    }


def _evaluate_pivot(
    db: Session,
    *,
    user_id: str,
    location: str,
    base_target_job: str,
    base_market_trend_score: float,
) -> tuple[str, bool, str, float]:
    best_job = base_target_job
    best_delta = 0.0

    for candidate in PIVOT_ROLE_CANDIDATES:
        if candidate.lower() == base_target_job.lower():
            continue
        candidate_stress = compute_market_stress_test(
            db,
            user_id=user_id,
            target_job=candidate,
            location=location,
        )
        candidate_market = float(candidate_stress.get("components", {}).get("market_trend_score", 0.0))
        delta = candidate_market - base_market_trend_score
        if delta > best_delta:
            best_delta = delta
            best_job = candidate

    if best_delta >= PIVOT_THRESHOLD_DELTA:
        reason = f"Pivot applied: {best_job} demand is +{best_delta:.1f} points above {base_target_job}."
        return best_job, True, reason, round(best_delta, 1)

    reason = f"Pivot not applied: best alternative improved demand by only +{best_delta:.1f} (< {PIVOT_THRESHOLD_DELTA:.0f})."
    return base_target_job, False, reason, round(best_delta, 1)


def run_ai_career_orchestrator(
    db: Session,
    *,
    user_id: str,
    target_job: str,
    location: str,
    availability_hours_per_week: int = 20,
    pivot_requested: bool = False,
) -> dict[str, Any]:
    stress = compute_market_stress_test(
        db,
        user_id=user_id,
        target_job=target_job,
        location=location,
    )
    resume_summary = build_user_resume_summary(db, user_id)
    base_market_trend_score = float(stress.get("components", {}).get("market_trend_score", 0.0))

    effective_target_job = target_job
    pivot_applied = False
    pivot_reason = "Pivot not requested."
    pivot_delta = 0.0
    if pivot_requested:
        effective_target_job, pivot_applied, pivot_reason, pivot_delta = _evaluate_pivot(
            db,
            user_id=user_id,
            location=location,
            base_target_job=target_job,
            base_market_trend_score=base_market_trend_score,
        )

    missing_skills = list(stress.get("missing_skills") or [])
    auditor_payload = {
        "target_job": effective_target_job,
        "location": location,
        "required_skills_count": stress.get("required_skills_count", 0),
        "missing_skills": missing_skills,
        "resume_summary": resume_summary,
    }
    planner_payload = {
        "target_job": effective_target_job,
        "location": location,
        "availability_hours_per_week": availability_hours_per_week,
        "missing_skills": missing_skills[:3],
        "market_trend_score": base_market_trend_score,
    }
    strategist_payload = {
        "target_job": effective_target_job,
        "location": location,
        "market_trend_score": base_market_trend_score,
        "vacancy_trend_label": stress.get("vacancy_trend_label", "neutral"),
        "pivot_requested": pivot_requested,
        "pivot_applied": pivot_applied,
    }

    auditor = _call_json_agent(
        (
            "You are The Auditor. Analyze skill gaps from federal standards and context. "
            "Return JSON with keys: top_missing_skills (max 3), rationale (string)."
        ),
        auditor_payload,
    )
    planner = _call_json_agent(
        (
            "You are The Planner. Create a 90-day execution curriculum. "
            "Every task must be concrete and formatted as 'Day X: ... because ...'. "
            "Return JSON keys: day_0_30, day_31_60, day_61_90, weekly_checkboxes."
        ),
        planner_payload,
    )
    strategist = _call_json_agent(
        (
            "You are The Strategist. Use market trend and vacancy direction to produce a 2-sentence alert. "
            "Return JSON keys: market_alert, risk_level."
        ),
        strategist_payload,
    )

    planner_day_0_30 = _as_list(planner.get("day_0_30"))
    planner_day_31_60 = _as_list(planner.get("day_31_60"))
    planner_day_61_90 = _as_list(planner.get("day_61_90"))
    planner_weekly = _as_list(planner.get("weekly_checkboxes"))
    if not (planner_day_0_30 or planner_day_31_60 or planner_day_61_90):
        defaults = _default_mission(missing_skills, effective_target_job, location)
        planner_day_0_30 = defaults["day_0_30"]
        planner_day_31_60 = defaults["day_31_60"]
        planner_day_61_90 = defaults["day_61_90"]
        planner_weekly = defaults["weekly_checkboxes"]

    top_missing_skills = _as_list(auditor.get("top_missing_skills")) or missing_skills[:3]
    market_alert = str(
        strategist.get("market_alert")
        or f"Demand for {effective_target_job} is shifting. Prioritize verified, market-aligned project proofs."
    ).strip()

    output = {
        "stress_test": stress,
        "auditor": {
            "top_missing_skills": top_missing_skills,
            "rationale": str(auditor.get("rationale") or "Prioritize highest-impact skill gaps first."),
        },
        "planner": {
            "day_0_30": planner_day_0_30,
            "day_31_60": planner_day_31_60,
            "day_61_90": planner_day_61_90,
            "weekly_checkboxes": planner_weekly,
        },
        "strategist": {
            "market_alert": market_alert,
            "risk_level": str(strategist.get("risk_level") or "medium"),
        },
        "mission_dashboard": {
            "day_0_30": planner_day_0_30,
            "day_31_60": planner_day_31_60,
            "day_61_90": planner_day_61_90,
            "weekly_checkboxes": planner_weekly,
        },
        "market_alert": market_alert,
        "top_missing_skills": top_missing_skills,
        "pivot_applied": pivot_applied,
        "pivot_reason": pivot_reason,
        "pivot_target_role": effective_target_job,
        "pivot_delta": pivot_delta,
    }

    _log_ai_audit(
        db,
        user_id=user_id,
        feature="ai_orchestrator",
        prompt_input={
            "target_job": target_job,
            "effective_target_job": effective_target_job,
            "location": location,
            "availability_hours_per_week": availability_hours_per_week,
            "pivot_requested": pivot_requested,
            "pivot_applied": pivot_applied,
        },
        context_ids=[],
        output=json.dumps(output)[:6000],
        model=get_active_ai_model(),
    )
    return output
