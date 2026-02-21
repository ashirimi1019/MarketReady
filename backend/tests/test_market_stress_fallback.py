from pathlib import Path
import sys

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services import market_stress as ms


class DummyDB:
    def rollback(self):
        return None


def _stress_snapshot_payload() -> dict:
    return {
        "score": 72.5,
        "mri_formula": ms.MRI_FORMULA,
        "mri_formula_version": ms.MRI_FORMULA_VERSION,
        "computed_at": "2026-02-21T00:00:00Z",
        "components": {
            "skill_overlap_score": 70.0,
            "market_trend_score": 75.0,
            "evidence_verification_score": 72.0,
        },
        "weights": {"skill_overlap": 0.4, "market_trend": 0.3, "evidence_verification": 0.3},
        "required_skills_count": 20,
        "matched_skills_count": 14,
        "missing_skills": ["system design"],
        "salary_average": 100000.0,
        "salary_percentile_local": 60.0,
        "top_hiring_companies": [{"name": "Acme", "open_roles": 3}],
        "vacancy_growth_percent": 5.0,
        "market_volatility_score": 35.0,
        "vacancy_trend_label": "heating_up",
        "job_stability_score_2027": 78.0,
        "data_freshness": "live",
        "provider_status": {"adzuna": "ok", "careeronestop": "ok"},
        "market_volatility_points": [{"x": 0.0, "y": 1.0}],
        "evidence_counts": {"verified": 1, "repo_verified": 1, "total": 1},
        "simulation_2027": {"projected_score": 68.0, "delta": -4.5, "risk_level": "medium", "at_risk_skills": [], "growth_skills": []},
        "citations": [],
    }


def test_provider_failure_uses_snapshot_fallback(monkeypatch):
    monkeypatch.setattr(ms, "fetch_careeronestop_skills", lambda _target_job: (_ for _ in ()).throw(RuntimeError("careeronestop down")))
    monkeypatch.setattr(
        ms,
        "_load_snapshot",
        lambda _db, source, **_kwargs: {"payload": _stress_snapshot_payload(), "snapshot_timestamp": "2026-02-21T01:00:00Z", "snapshot_age_minutes": 12.0}
        if source == ms.SNAPSHOT_SOURCE_STRESS
        else None,
    )

    result = ms.compute_market_stress_test(
        DummyDB(),
        user_id="user-1",
        target_job="software engineer",
        location="atlanta, ga",
    )

    assert result["source_mode"] == "snapshot_fallback"
    assert result["snapshot_timestamp"] == "2026-02-21T01:00:00Z"
    assert result["provider_status"]["adzuna"] == "snapshot_fallback"
    assert result["provider_status"]["careeronestop"] == "snapshot_fallback"
    assert "adzuna_query_mode" in result


def test_expired_or_missing_snapshot_raises_provider_error(monkeypatch):
    monkeypatch.setattr(ms, "fetch_careeronestop_skills", lambda _target_job: (_ for _ in ()).throw(RuntimeError("CareerOneStop skills matcher failed or timed out.")))
    monkeypatch.setattr(ms, "_load_snapshot", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match="CareerOneStop skills matcher failed or timed out"):
        ms.compute_market_stress_test(
            DummyDB(),
            user_id="user-2",
            target_job="software engineer",
            location="atlanta, ga",
        )
