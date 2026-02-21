from pathlib import Path
import sys

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services import market_stress as ms


def _history_points(values: list[float]) -> list[dict[str, float]]:
    return [{"x": float(idx), "y": float(value)} for idx, value in enumerate(values)]


def _set_static_downstream(monkeypatch):
    monkeypatch.setattr(ms.settings, "adzuna_app_id", "test-app-id")
    monkeypatch.setattr(ms.settings, "adzuna_app_key", "test-app-key")
    monkeypatch.setattr(ms.settings, "adzuna_country", "us")
    monkeypatch.setattr(ms, "_fetch_histogram_metrics", lambda *_args, **_kwargs: (95000.0, 100, 62.0))
    monkeypatch.setattr(ms, "_fetch_top_hiring_companies", lambda *_args, **_kwargs: [{"name": "Acme", "open_roles": 3}])


def test_adzuna_exact_history_success(monkeypatch):
    _set_static_downstream(monkeypatch)
    monkeypatch.setattr(
        ms,
        "_fetch_history_points",
        lambda *_args, **kwargs: _history_points([100, 110, 130]) if kwargs["what"] == "software engineer" and kwargs["where"] == "United States" else [],
    )

    result = ms.fetch_adzuna_benchmarks("software engineer", "United States")

    assert result.adzuna_query_mode == "exact"
    assert result.adzuna_query_used == "software engineer"
    assert result.adzuna_location_used == "United States"
    assert len(result.volatility_points) >= 2


def test_adzuna_role_rewrite_recovery(monkeypatch):
    _set_static_downstream(monkeypatch)

    def fake_history(*_args, **kwargs):
        if kwargs["what"] == "backend developer" and kwargs["where"] == "United States":
            return _history_points([80, 95, 105])
        return []

    monkeypatch.setattr(ms, "_fetch_history_points", fake_history)

    result = ms.fetch_adzuna_benchmarks("backend engineer", "United States")

    assert result.adzuna_query_mode == "role_rewrite"
    assert result.adzuna_query_used == "backend developer"
    assert result.adzuna_location_used == "United States"
    assert len(result.volatility_points) >= 2


def test_adzuna_geo_widen_recovery(monkeypatch):
    _set_static_downstream(monkeypatch)

    def fake_history(*_args, **kwargs):
        if kwargs["what"] == "software engineer" and kwargs["where"] == "United States":
            return _history_points([100, 102, 106])
        return []

    monkeypatch.setattr(ms, "_fetch_history_points", fake_history)

    result = ms.fetch_adzuna_benchmarks("software engineer", "Roswell, GA")

    assert result.adzuna_query_mode == "geo_widen"
    assert result.adzuna_query_used == "software engineer"
    assert result.adzuna_location_used == "United States"
    assert len(result.volatility_points) >= 2


def test_adzuna_proxy_from_search_recovery(monkeypatch):
    _set_static_downstream(monkeypatch)
    monkeypatch.setattr(ms, "_fetch_history_points", lambda *_args, **_kwargs: [])

    def fake_search_count(*_args, **kwargs):
        role = kwargs["what"]
        where = kwargs["where"]
        days = kwargs["max_days_old"]
        if role == "backend developer" and where == "United States":
            return {30: 3000, 14: 1700, 7: 980, 3: 510, 1: 180}.get(days, 0.0)
        return 0.0

    monkeypatch.setattr(ms, "_fetch_search_count", fake_search_count)
    monkeypatch.setattr(
        ms,
        "_compute_proxy_from_search",
        lambda *_args, **_kwargs: {
            "vacancy_index": 90.0,
            "vacancy_growth_percent": 20.0,
            "volatility_score": 12.0,
            "trend_label": "heating_up",
            "volatility_points": _history_points([100, 110, 120, 140, 180]),
        },
    )

    result = ms.fetch_adzuna_benchmarks("backend engineer", "Roswell, GA")

    assert result.adzuna_query_mode == "proxy_from_search"
    assert result.adzuna_query_used == "backend developer"
    assert result.adzuna_location_used == "United States"
    assert len(result.volatility_points) >= 2
    assert result.vacancy_index == 90.0


def test_adzuna_full_failure_without_snapshot_raises(monkeypatch):
    _set_static_downstream(monkeypatch)
    monkeypatch.setattr(ms, "_fetch_history_points", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(ms, "_fetch_search_count", lambda *_args, **_kwargs: 0.0)

    with pytest.raises(RuntimeError, match="Adzuna benchmarks unavailable"):
        ms.fetch_adzuna_benchmarks("backend engineer", "Roswell, GA")
