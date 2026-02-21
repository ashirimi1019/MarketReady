from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services import market_stress as ms


class DummyDB:
    def rollback(self):
        return None


def _bench(vacancy_index: float) -> ms.MarketBenchmarks:
    return ms.MarketBenchmarks(
        salary_avg=90000.0,
        vacancy_index=vacancy_index,
        trend_label="heating_up",
        volatility_points=[{"x": 0.0, "y": 100.0}, {"x": 1.0, "y": 120.0}],
    )


def test_mri_formula_uses_weighted_components(monkeypatch):
    monkeypatch.setattr(ms, "fetch_careeronestop_skills", lambda _target_job: ["python", "sql", "rest api", "cloud fundamentals"])
    monkeypatch.setattr(ms, "fetch_adzuna_benchmarks", lambda _target_job, _location: _bench(80.0))
    monkeypatch.setattr(ms, "_load_verified_skill_names", lambda _db, _user_id: {"python", "sql"})
    monkeypatch.setattr(ms, "_evidence_verification_score", lambda _db, _user_id: (50.0, {"verified": 1, "repo_verified": 1, "total": 2}))
    monkeypatch.setattr(ms, "_save_snapshot", lambda *_args, **_kwargs: {"snapshot_timestamp": "2026-02-21T00:00:00Z", "snapshot_age_minutes": 0.0})

    result = ms.compute_market_stress_test(
        DummyDB(),
        user_id="user-1",
        target_job="software engineer",
        location="atlanta, ga",
    )

    assert result["components"]["skill_overlap_score"] == 50.0
    assert result["components"]["market_trend_score"] == 80.0
    assert result["components"]["evidence_verification_score"] == 50.0
    assert result["score"] == 59.0


def test_major_scores_are_clamped_to_0_100(monkeypatch):
    monkeypatch.setattr(ms, "fetch_careeronestop_skills", lambda _target_job: ["python"])
    monkeypatch.setattr(ms, "_load_verified_skill_names", lambda _db, _user_id: {"python"})
    monkeypatch.setattr(ms, "_save_snapshot", lambda *_args, **_kwargs: {"snapshot_timestamp": "2026-02-21T00:00:00Z", "snapshot_age_minutes": 0.0})

    monkeypatch.setattr(ms, "_evidence_verification_score", lambda _db, _user_id: (250.0, {"verified": 1, "repo_verified": 1, "total": 1}))
    monkeypatch.setattr(ms, "fetch_adzuna_benchmarks", lambda _target_job, _location: _bench(500.0))
    high_case = ms.compute_market_stress_test(
        DummyDB(),
        user_id="user-2",
        target_job="software engineer",
        location="us",
    )
    assert high_case["score"] == 100.0
    assert high_case["components"]["market_trend_score"] == 100.0
    assert high_case["components"]["evidence_verification_score"] == 100.0

    monkeypatch.setattr(ms, "_evidence_verification_score", lambda _db, _user_id: (-20.0, {"verified": 0, "repo_verified": 0, "total": 1}))
    monkeypatch.setattr(ms, "fetch_adzuna_benchmarks", lambda _target_job, _location: _bench(-80.0))
    low_case = ms.compute_market_stress_test(
        DummyDB(),
        user_id="user-3",
        target_job="software engineer",
        location="us",
    )
    assert low_case["score"] == 40.0
    assert low_case["components"]["market_trend_score"] == 0.0
    assert low_case["components"]["evidence_verification_score"] == 0.0
