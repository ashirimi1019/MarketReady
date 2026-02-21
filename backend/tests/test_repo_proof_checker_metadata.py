from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models.entities import Proof
from app.services import market_stress as ms


class FakeQuery:
    def __init__(self, proof: SimpleNamespace):
        self._proof = proof

    def filter(self, *_args, **_kwargs):
        return self

    def one_or_none(self):
        return self._proof


class DummyDB:
    def __init__(self, proof: SimpleNamespace):
        self._proof = proof
        self.commits = 0

    def query(self, _model):
        return FakeQuery(self._proof)

    def commit(self):
        self.commits += 1

    def rollback(self):
        return None


def _bench() -> ms.MarketBenchmarks:
    return ms.MarketBenchmarks(
        salary_avg=95000.0,
        vacancy_index=72.0,
        trend_label="heating_up",
        volatility_points=[{"x": 0.0, "y": 100.0}, {"x": 1.0, "y": 120.0}],
    )


def test_repo_metadata_is_persisted(monkeypatch):
    proof = SimpleNamespace(id="proof-1", user_id="user-1", metadata_json={})
    db = DummyDB(proof)

    monkeypatch.setattr(ms, "fetch_careeronestop_skills", lambda _target_job: ["python", "rest api"])
    monkeypatch.setattr(ms, "fetch_adzuna_benchmarks", lambda _target_job, _location: _bench())
    monkeypatch.setattr(ms, "_save_snapshot", lambda *_args, **_kwargs: {"snapshot_timestamp": "2026-02-21T00:00:00Z", "snapshot_age_minutes": 0.0})
    monkeypatch.setattr(
        ms,
        "verify_repo_against_skills",
        lambda _repo_url, _required_skills: {
            "matched_skills": ["python"],
            "confidence": 50.0,
            "files_checked": ["demo-repo/README.md"],
            "repos_checked": ["demo-repo"],
            "languages_detected": ["python"],
        },
    )

    out = ms.repo_proof_checker(
        db,
        user_id="user-1",
        target_job="backend engineer",
        location="atlanta, ga",
        repo_url="https://github.com/example/demo-repo",
        proof_id="proof-1",
    )

    assert out["source_mode"] == "live"
    assert out["match_count"] == 1
    assert proof.metadata_json["repo_verified"] is True
    assert proof.metadata_json["repo_matched_skills"] == ["python"]
    assert proof.metadata_json["repo_confidence"] == 50.0
    assert db.commits >= 1
