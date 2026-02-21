from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import (
    ChecklistItem,
    ChecklistVersion,
    Proof,
    Skill,
    StudentProfile,
    UserPathway,
)

MRI_FORMULA = "MRI = (0.40 * Skill Match) + (0.30 * Market Demand) + (0.30 * Proof Density)"
MRI_FORMULA_VERSION = "2026.1"


@dataclass
class MarketBenchmarks:
    salary_avg: float | None
    vacancy_index: float
    trend_label: str
    volatility_points: list[dict[str, float]]
    history_points_found: int = 0
    salary_points_found: int = 0


def _normalize_skill(text: str) -> str:
    return " ".join(
        (text or "")
        .strip()
        .lower()
        .replace("_", " ")
        .replace("-", " ")
        .replace("/", " ")
        .split()
    )


def _canonical_token(token: str) -> str:
    value = (token or "").strip().lower()
    if len(value) > 4 and value.endswith("s"):
        value = value[:-1]
    return value


SKILL_ALIASES: dict[str, set[str]] = {
    "rest api": {"rest api", "restful api", "fastapi", "express", "flask"},
    "python": {"python", "py", "fastapi", "django"},
    "javascript": {"javascript", "node", "nodejs", "express"},
    "typescript": {"typescript", "ts-node", "tsconfig", "next.js"},
    "sql": {"sql", "postgresql", "mysql", "sqlite"},
    "cloud fundamentals": {"cloud fundamentals", "aws", "azure", "gcp", "terraform"},
    "cybersecurity": {"cybersecurity", "threat hunting", "siem", "splunk", "security"},
}

LOW_RESILIENCE_TOKENS = (
    "manual testing",
    "basic html",
    "basic css",
    "vanilla coding",
    "documentation",
    "log monitoring",
    "frontend fundamentals",
)
HIGH_RESILIENCE_TOKENS = (
    "system design",
    "architecture",
    "rag",
    "prompt engineering",
    "cybersecurity",
    "threat hunting",
    "ethical ai",
    "compliance",
    "cloud",
    "distributed systems",
)


def fetch_adzuna_benchmarks(target_job: str, location: str) -> MarketBenchmarks:
    if not settings.adzuna_app_id or not settings.adzuna_app_key:
        raise RuntimeError("Adzuna is not configured. Set ADZUNA_APP_ID and ADZUNA_APP_KEY.")

    what = (target_job or "software engineer").strip()
    where = (location or "united states").strip()
    country = settings.adzuna_country
    timeout = 12.0
    base = "https://api.adzuna.com/v1/api/jobs"

    salary_avg: float | None = None
    vacancy_index = 0.0
    volatility_points: list[dict[str, float]] = []
    history_points_found = 0
    salary_points_found = 0

    with httpx.Client(timeout=timeout) as client:
        try:
            hist = client.get(
                f"{base}/{country}/history",
                params={
                    "app_id": settings.adzuna_app_id,
                    "app_key": settings.adzuna_app_key,
                    "what": what,
                    "where": where,
                    "months": 6,
                },
            )
            hist.raise_for_status()
            rows = hist.json().get("month") or hist.json().get("results") or []
            for idx, row in enumerate(rows):
                count = float(row.get("count") or row.get("vacancies") or 0)
                volatility_points.append({"x": float(idx), "y": count})
            history_points_found = len(volatility_points)
            if len(volatility_points) >= 2:
                first = max(volatility_points[0]["y"], 1.0)
                last = volatility_points[-1]["y"]
                vacancy_index = max(0.0, min(100.0, (last / first) * 50.0))
        except Exception:
            raise RuntimeError("Adzuna history endpoint failed or timed out.")

        try:
            histo = client.get(
                f"{base}/{country}/histogram",
                params={
                    "app_id": settings.adzuna_app_id,
                    "app_key": settings.adzuna_app_key,
                    "what": what,
                    "where": where,
                },
            )
            histo.raise_for_status()
            payload = histo.json()
            buckets = payload.get("salary_is_predicted") or payload.get("histogram") or payload.get("results") or {}
            if isinstance(buckets, dict) and buckets:
                weighted_sum = 0.0
                total = 0.0
                for key, value in buckets.items():
                    try:
                        salary = float(str(key).split("-")[0])
                        cnt = float(value)
                    except Exception:
                        continue
                    weighted_sum += salary * cnt
                    total += cnt
                if total > 0:
                    salary_avg = weighted_sum / total
                    salary_points_found = int(total)
        except Exception:
            raise RuntimeError("Adzuna histogram endpoint failed or timed out.")

    trend_label = "heating_up" if vacancy_index >= 60 else "cooling_down" if vacancy_index <= 40 else "neutral"
    if not volatility_points:
        raise RuntimeError("Adzuna returned no volatility points for this query.")
    return MarketBenchmarks(
        salary_avg=salary_avg,
        vacancy_index=round(vacancy_index, 2),
        trend_label=trend_label,
        volatility_points=volatility_points,
        history_points_found=history_points_found,
        salary_points_found=salary_points_found,
    )


def fetch_careeronestop_skills(target_job: str) -> list[str]:
    if not settings.careeronestop_api_key or not settings.careeronestop_user_id:
        raise RuntimeError("CareerOneStop is not configured. Set CAREERONESTOP_API_KEY and CAREERONESTOP_USER_ID.")

    job = quote((target_job or "software developer").strip(), safe="")
    timeout = 20.0
    headers = {"Authorization": f"Bearer {settings.careeronestop_api_key}"}
    occ_url = (
        "https://api.careeronestop.org/v1/occupation/"
        f"{settings.careeronestop_user_id}/{job}/US/0/10"
    )

    try:
        with httpx.Client(timeout=timeout) as client:
            occ_response = client.get(occ_url, headers=headers)
            occ_response.raise_for_status()
            occ_payload = occ_response.json()
            occupation_rows = (
                occ_payload.get("OccupationList")
                or occ_payload.get("OccupationDetailList")
                or occ_payload.get("Occupations")
                or []
            )
            if not occupation_rows:
                raise RuntimeError("CareerOneStop returned no occupations for this target role.")

            normalized_target_job = _normalize_skill(target_job or "software developer")
            target_tokens = {
                _canonical_token(token)
                for token in normalized_target_job.split()
                if token and token not in {"and", "or", "the", "a", "an", "of"}
            }
            lead_target_token = normalized_target_job.split()[0] if normalized_target_job.split() else ""
            best_row: dict[str, Any] | None = None
            best_score = -1.0
            for row in occupation_rows:
                if not isinstance(row, dict):
                    continue
                title = _normalize_skill(str(row.get("OnetTitle") or row.get("Title") or ""))
                if not title:
                    continue
                title_tokens = {_canonical_token(token) for token in title.split() if token}
                overlap = len(target_tokens & title_tokens)
                direct = 1 if lead_target_token and title.startswith(lead_target_token) else 0
                score = (overlap * 2.0) + direct
                if score > best_score:
                    best_score = score
                    best_row = row

            first = best_row or (occupation_rows[0] if isinstance(occupation_rows[0], dict) else {})
            onet_code = str(
                first.get("OnetCode")
                or first.get("OccupationCode")
                or first.get("Code")
                or ""
            ).strip()
            if not onet_code:
                raise RuntimeError("CareerOneStop occupation response did not include an O*NET code.")

            detail_url = (
                "https://api.careeronestop.org/v1/occupation/"
                f"{settings.careeronestop_user_id}/{quote(onet_code, safe='')}/US"
            )
            detail_response = client.get(
                detail_url,
                headers=headers,
                params={
                    "skills": "true",
                    "knowledge": "true",
                    "ability": "true",
                },
            )
            detail_response.raise_for_status()
            detail_payload = detail_response.json()
    except Exception:
        raise RuntimeError("CareerOneStop skills matcher failed or timed out.")

    detail_rows = detail_payload.get("OccupationDetail") or []
    detail = detail_rows[0] if detail_rows and isinstance(detail_rows[0], dict) else {}
    ranked: list[tuple[float, str]] = []

    for key in ("SkillsDataList", "KnowledgeDataList"):
        rows = detail.get(key) or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            raw_name = row.get("ElementName") or row.get("Skill") or row.get("name")
            if not raw_name:
                continue
            norm = _normalize_skill(str(raw_name))
            if not norm:
                continue
            try:
                importance = float(row.get("Importance") or row.get("DataValue") or 0.0)
            except Exception:
                importance = 0.0
            ranked.append((importance, norm))

    if not ranked:
        for row in occupation_rows:
            if not isinstance(row, dict):
                continue
            text = " ".join(
                str(row.get(key) or "")
                for key in ("OnetTitle", "OccupationDescription", "Duties", "BrightOutlook")
            ).lower()
            for canonical, aliases in SKILL_ALIASES.items():
                alias_pool = set(aliases) | {canonical}
                if any(alias in text for alias in alias_pool if alias):
                    ranked.append((10.0, canonical))

    ranked.sort(key=lambda item: item[0], reverse=True)
    out: list[str] = []
    for _, norm in ranked:
        if norm and norm not in out:
            out.append(norm)
        if len(out) >= 40:
            break
    if not out:
        raise RuntimeError("CareerOneStop returned no required skills for this role.")
    return out


def _load_verified_skill_names(db: Session, user_id: str) -> set[str]:
    selection = (
        db.query(UserPathway)
        .filter(UserPathway.user_id == user_id)
        .order_by(UserPathway.selected_at.desc())
        .first()
    )
    if not selection or not selection.checklist_version_id:
        return set()

    version = db.query(ChecklistVersion).filter(ChecklistVersion.id == selection.checklist_version_id).one_or_none()
    if not version:
        return set()

    items = (
        db.query(ChecklistItem, Skill)
        .outerjoin(Skill, ChecklistItem.skill_id == Skill.id)
        .filter(ChecklistItem.version_id == version.id)
        .all()
    )
    verified_item_ids = {
        str(p.checklist_item_id)
        for p in db.query(Proof).filter(Proof.user_id == user_id, Proof.status == "verified").all()
    }
    names: set[str] = set()
    for item, skill in items:
        if str(item.id) not in verified_item_ids:
            continue
        if skill and skill.name:
            names.add(_normalize_skill(skill.name))
        names.add(_normalize_skill(item.title))
    return {n for n in names if n}


def _evidence_verification_score(db: Session, user_id: str) -> tuple[float, dict[str, int]]:
    proofs = db.query(Proof).filter(Proof.user_id == user_id).all()
    if not proofs:
        return 0.0, {"verified": 0, "repo_verified": 0, "total": 0}

    total = len(proofs)
    verified = sum(1 for p in proofs if p.status == "verified")
    repo_verified = 0
    for proof in proofs:
        meta = proof.metadata_json if isinstance(proof.metadata_json, dict) else {}
        if bool(meta.get("repo_verified")):
            repo_verified += 1

    ratio = ((verified / total) * 0.7) + ((repo_verified / total) * 0.3)
    return round(max(0.0, min(100.0, ratio * 100.0)), 2), {
        "verified": verified,
        "repo_verified": repo_verified,
        "total": total,
    }


def _skill_resilience_multiplier(skill_name: str) -> float:
    skill = _normalize_skill(skill_name)
    if any(token in skill for token in LOW_RESILIENCE_TOKENS):
        return 0.5
    if any(token in skill for token in HIGH_RESILIENCE_TOKENS):
        return 1.7
    return 1.0


def _build_2027_simulation(
    current_score: float,
    required_skills: list[str],
    verified_skill_names: set[str],
    market_trend_score: float,
) -> dict[str, Any]:
    total_weight = 0.0
    weighted_skill_value = 0.0
    at_risk: list[str] = []
    growth: list[str] = []
    seen_at_risk: set[str] = set()
    seen_growth: set[str] = set()

    for raw_skill in required_skills:
        skill = _normalize_skill(raw_skill)
        if not skill:
            continue
        multiplier = _skill_resilience_multiplier(skill)
        base = 1.0 if skill in verified_skill_names else 0.35
        total_weight += 1.0
        weighted_skill_value += base * multiplier
        if multiplier <= 0.6 and skill in verified_skill_names and skill not in seen_at_risk:
            at_risk.append(skill)
            seen_at_risk.add(skill)
        if multiplier >= 1.5 and skill not in seen_growth:
            growth.append(skill)
            seen_growth.add(skill)

    skill_component = (weighted_skill_value / total_weight) * 50.0 if total_weight > 0 else 0.0
    market_component = max(0.0, min(100.0, market_trend_score)) * 0.5
    projected_score = max(0.0, min(100.0, round(skill_component + market_component, 1)))
    delta = round(projected_score - current_score, 1)
    risk_level = "high" if projected_score < 60 else "medium" if projected_score < 78 else "low"

    return {
        "projected_score": projected_score,
        "delta": delta,
        "risk_level": risk_level,
        "at_risk_skills": at_risk[:8],
        "growth_skills": growth[:8],
    }


def compute_market_stress_test(
    db: Session,
    *,
    user_id: str,
    target_job: str,
    location: str,
) -> dict[str, Any]:
    provider_status: dict[str, str] = {"adzuna": "ok", "careeronestop": "ok"}
    data_freshness = "live"

    required_skills = fetch_careeronestop_skills(target_job)
    verified_skill_names = _load_verified_skill_names(db, user_id)
    benchmarks = fetch_adzuna_benchmarks(target_job, location)

    if required_skills:
        overlap_count = len({skill for skill in required_skills if skill in verified_skill_names})
        skill_overlap_score = (overlap_count / len(required_skills)) * 100.0
    else:
        overlap_count = 0
        skill_overlap_score = 0.0

    evidence_score, evidence_counts = _evidence_verification_score(db, user_id)
    market_trend_score = benchmarks.vacancy_index
    salary_momentum = 50.0
    if benchmarks.salary_avg and benchmarks.salary_avg > 0:
        salary_momentum = 55.0 if benchmarks.salary_avg >= 60000 else 45.0

    slope_component = 100.0 if benchmarks.trend_label == "heating_up" else 20.0 if benchmarks.trend_label == "cooling_down" else 55.0
    job_stability_score_2027 = round(
        max(0.0, min(100.0, (0.7 * market_trend_score) + (0.3 * ((salary_momentum + slope_component) / 2.0)))),
        2,
    )

    final_score = (0.40 * skill_overlap_score) + (0.30 * evidence_score) + (0.30 * market_trend_score)
    final_score = round(max(0.0, min(100.0, final_score)), 2)
    simulation_2027 = _build_2027_simulation(final_score, required_skills, verified_skill_names, market_trend_score)

    missing_skills = [skill for skill in required_skills if skill not in verified_skill_names][:10]
    citations = [
        {
            "source": "CareerOneStop Skills Matcher",
            "signal": "required_skill_overlap",
            "value": f"{overlap_count}/{len(required_skills)}",
            "note": "Federal skill-standard overlap for the target role.",
        },
        {
            "source": "Adzuna History/Histogram",
            "signal": "market_trend_score",
            "value": round(market_trend_score, 2),
            "note": "Local vacancy momentum and salary signal.",
        },
        {
            "source": "Proof + GitHub verification",
            "signal": "proof_density",
            "value": round(evidence_score, 2),
            "note": "Evidence quality from verified submissions and repo checks.",
        },
    ]

    return {
        "score": final_score,
        "mri_formula": MRI_FORMULA,
        "mri_formula_version": MRI_FORMULA_VERSION,
        "computed_at": datetime.utcnow().isoformat() + "Z",
        "components": {
            "skill_overlap_score": round(skill_overlap_score, 2),
            "evidence_verification_score": evidence_score,
            "market_trend_score": round(market_trend_score, 2),
        },
        "weights": {
            "skill_overlap": 0.40,
            "evidence_verification": 0.30,
            "market_trend": 0.30,
        },
        "required_skills_count": len(required_skills),
        "matched_skills_count": overlap_count,
        "missing_skills": missing_skills,
        "salary_average": benchmarks.salary_avg,
        "vacancy_trend_label": benchmarks.trend_label,
        "job_stability_score_2027": job_stability_score_2027,
        "data_freshness": data_freshness,
        "provider_status": provider_status,
        "market_volatility_points": benchmarks.volatility_points,
        "evidence_counts": evidence_counts,
        "simulation_2027": simulation_2027,
        "citations": citations,
    }


def _repo_owner_name(repo_url: str) -> tuple[str, str] | None:
    cleaned = (repo_url or "").strip().rstrip("/")
    if "github.com/" not in cleaned:
        return None
    try:
        tail = cleaned.split("github.com/", 1)[1]
        parts = [part for part in tail.split("/") if part]
        if not parts:
            return None
        owner = parts[0]
        repo = parts[1].replace(".git", "") if len(parts) > 1 else ""
        if owner:
            return owner, repo
    except Exception:
        return None
    return None


def _fetch_owner_repos(client: httpx.Client, owner: str) -> list[str]:
    try:
        response = client.get(
            f"https://api.github.com/users/{owner}/repos",
            params={"per_page": 30, "sort": "updated", "direction": "desc", "type": "owner"},
        )
        if response.status_code != 200:
            return []
        payload = response.json()
        if not isinstance(payload, list):
            return []
        repos: list[str] = []
        for row in payload:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or "").strip()
            if name and name not in repos:
                repos.append(name)
        return repos
    except Exception:
        return []


def _fetch_repo_languages(client: httpx.Client, owner: str, repo: str) -> set[str]:
    try:
        response = client.get(f"https://api.github.com/repos/{owner}/{repo}/languages")
        if response.status_code != 200:
            return set()
        payload = response.json()
        if not isinstance(payload, dict):
            return set()
        return {str(name).lower() for name in payload.keys() if str(name).strip()}
    except Exception:
        return set()


def verify_repo_against_skills(repo_url: str, required_skills: list[str]) -> dict[str, Any]:
    parsed = _repo_owner_name(repo_url)
    if not parsed:
        return {
            "matched_skills": [],
            "confidence": 0.0,
            "files_checked": [],
            "repos_checked": [],
            "languages_detected": [],
        }

    owner, repo = parsed
    headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
    files_to_check = ["README.md", "readme.md", "package.json", "requirements.txt", "pyproject.toml"]
    checked: list[str] = []
    corpus: list[str] = []
    repos_checked: list[str] = []
    languages_detected: set[str] = set()

    with httpx.Client(timeout=5.0, headers=headers) as client:
        target_repos = [repo] if repo else []
        if not target_repos:
            target_repos = _fetch_owner_repos(client, owner)[:8]

        for repo_name in target_repos:
            if not repo_name:
                continue
            repos_checked.append(repo_name)
            languages_detected.update(_fetch_repo_languages(client, owner, repo_name))
            for file_name in files_to_check:
                try:
                    url = f"https://raw.githubusercontent.com/{owner}/{repo_name}/HEAD/{file_name}"
                    response = client.get(url)
                    if response.status_code == 200 and response.text:
                        checked.append(f"{repo_name}/{file_name}")
                        corpus.append(response.text.lower())
                except Exception:
                    continue

    corpus.extend(languages_detected)
    combined = "\n".join(corpus)
    matched: list[str] = []
    for skill in required_skills:
        token = _normalize_skill(skill)
        alias_pool = {token}
        alias_pool.update(SKILL_ALIASES.get(token, set()))
        has_match = any(alias in combined for alias in alias_pool if alias)
        if token and has_match and token not in matched:
            matched.append(token)

    confidence = (len(matched) / max(len(required_skills), 1)) * 100.0
    return {
        "matched_skills": matched,
        "confidence": round(max(0.0, min(100.0, confidence)), 2),
        "files_checked": checked,
        "repos_checked": repos_checked,
        "languages_detected": sorted(languages_detected),
    }


def repo_proof_checker(
    db: Session,
    *,
    user_id: str,
    target_job: str,
    location: str,
    repo_url: str,
    proof_id: str | None = None,
) -> dict[str, Any]:
    required_skills = fetch_careeronestop_skills(target_job)
    repo_result = verify_repo_against_skills(repo_url, required_skills)

    if proof_id:
        proof = db.query(Proof).filter(Proof.id == proof_id, Proof.user_id == user_id).one_or_none()
        if proof:
            meta = proof.metadata_json if isinstance(proof.metadata_json, dict) else {}
            meta["repo_url"] = repo_url
            meta["repo_verified"] = bool(repo_result["matched_skills"])
            meta["repo_matched_skills"] = repo_result["matched_skills"]
            meta["repo_confidence"] = repo_result["confidence"]
            meta["repo_files_checked"] = repo_result["files_checked"]
            proof.metadata_json = meta
            db.commit()

    benchmark = fetch_adzuna_benchmarks(target_job, location)
    missing = [skill for skill in required_skills if skill not in set(repo_result["matched_skills"])]
    return {
        "repo_url": repo_url,
        "required_skills_count": len(required_skills),
        "matched_skills": repo_result["matched_skills"],
        "verified_by_repo_skills": repo_result["matched_skills"],
        "skills_required_but_missing": missing[:15],
        "match_count": len(repo_result["matched_skills"]),
        "repo_confidence": repo_result["confidence"],
        "files_checked": repo_result["files_checked"],
        "repos_checked": repo_result.get("repos_checked", []),
        "languages_detected": repo_result.get("languages_detected", []),
        "vacancy_trend_label": benchmark.trend_label,
    }


def build_user_resume_summary(db: Session, user_id: str) -> str:
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).one_or_none()
    if not profile:
        return ""
    parts = [
        f"University: {profile.university}" if profile.university else "",
        f"State: {profile.state}" if profile.state else "",
        f"Current stage: {profile.semester}" if profile.semester else "",
        f"GitHub: {profile.github_username}" if profile.github_username else "",
    ]
    return " | ".join([part for part in parts if part]).strip()
