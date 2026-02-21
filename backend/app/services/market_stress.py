from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import (
    ChecklistItem,
    ChecklistVersion,
    MarketRawIngestion,
    Proof,
    Skill,
    StudentProfile,
    UserPathway,
)

MRI_FORMULA = "MRI = (0.40 * Skill Match) + (0.30 * Market Demand) + (0.30 * Proof Density)"
MRI_FORMULA_VERSION = "2026.1"
SNAPSHOT_SOURCE_STRESS = "mri:stress:v1"
SNAPSHOT_SOURCE_SKILLS = "mri:skills:v1"
SNAPSHOT_SOURCE_ADZUNA = "mri:adzuna:v1"
SNAPSHOT_TTL_SKILLS_HOURS = 168
SNAPSHOT_TTL_ADZUNA_HOURS = 24
SNAPSHOT_TTL_STRESS_HOURS = 24
ADZUNA_PROXY_WINDOWS = (30, 14, 7, 3, 1)


@dataclass
class MarketBenchmarks:
    salary_avg: float | None
    vacancy_index: float
    trend_label: str
    volatility_points: list[dict[str, float]]
    adzuna_query_mode: str = "exact"
    adzuna_query_used: str | None = None
    adzuna_location_used: str | None = None
    history_points_found: int = 0
    salary_points_found: int = 0
    salary_percentile_local: float | None = None
    top_hiring_companies: list[dict[str, Any]] = field(default_factory=list)
    vacancy_growth_percent: float = 0.0
    volatility_score: float = 0.0


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

ADZUNA_ROLE_REWRITES: dict[str, list[str]] = {
    "backend engineer": ["backend developer", "software developer", "software engineer", "python developer"],
    "frontend developer": ["web developer", "javascript developer", "software engineer"],
    "frontend engineer": ["frontend developer", "web developer", "javascript developer"],
    "cybersecurity analyst": ["information security analyst", "security analyst", "cyber security analyst"],
    "cloud security engineer": ["security engineer", "cloud engineer", "devops engineer"],
    "ml engineer": ["machine learning engineer", "ai engineer", "data scientist"],
    "data engineer": ["data developer", "etl developer", "software engineer"],
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _clamp_score(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def _dedupe_strings(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw or "").strip()
        key = value.lower()
        if not value or key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _build_role_candidates(target_job: str) -> list[str]:
    base = (target_job or "software engineer").strip() or "software engineer"
    normalized = _normalize_skill(base)
    variants: list[str] = [base]
    variants.extend(ADZUNA_ROLE_REWRITES.get(normalized, []))

    if "engineer" in normalized:
        generic = " ".join("developer" if token == "engineer" else token for token in normalized.split())
        if generic:
            variants.append(generic)

    if "developer" in normalized and "software developer" not in [v.lower() for v in variants]:
        variants.append("software developer")
    if "software engineer" not in [v.lower() for v in variants]:
        variants.append("software engineer")

    return _dedupe_strings(variants)


def _build_location_candidates(location: str) -> list[str]:
    base = (location or "United States").strip() or "United States"
    variants: list[str] = [base]
    if "," in base:
        tail = base.split(",")[-1].strip()
        if tail:
            variants.append(tail)
    if base.lower() not in {"united states", "us", "usa"}:
        variants.append("United States")
    return _dedupe_strings(variants)


def _snapshot_key(target_job: str, location: str) -> str:
    job = _normalize_skill(target_job or "software engineer")
    where = _normalize_skill(location or "united states")
    return f"{job}|{where}"


def _format_snapshot_timestamp(value: datetime | None) -> str | None:
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_snapshot_timestamp(value: Any, fallback: datetime | None) -> datetime | None:
    text = str(value or "").strip()
    if text:
        cleaned = text[:-1] if text.endswith("Z") else text
        try:
            parsed = datetime.fromisoformat(cleaned)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            pass
    if fallback is None:
        return None
    if fallback.tzinfo is None:
        return fallback.replace(tzinfo=timezone.utc)
    return fallback.astimezone(timezone.utc)


def _snapshot_age_minutes(timestamp: datetime | None) -> float | None:
    if not timestamp:
        return None
    return round(max(0.0, (_utcnow() - timestamp).total_seconds() / 60.0), 1)


def _save_snapshot(db: Session, source: str, key: str, payload: dict[str, Any]) -> dict[str, Any]:
    stamp = _utcnow()
    row = MarketRawIngestion(
        source=source,
        metadata_json={
            "snapshot_key": key,
            "snapshot_timestamp": _format_snapshot_timestamp(stamp),
            "payload": payload,
        },
    )
    db.add(row)
    db.commit()
    return {
        "snapshot_timestamp": _format_snapshot_timestamp(stamp),
        "snapshot_age_minutes": 0.0,
    }


def _load_snapshot(
    db: Session,
    source: str,
    key: str,
    max_age_hours: int,
) -> dict[str, Any] | None:
    max_age_minutes = max(1, int(max_age_hours) * 60)
    rows = (
        db.query(MarketRawIngestion)
        .filter(MarketRawIngestion.source == source)
        .order_by(MarketRawIngestion.fetched_at.desc())
        .limit(250)
        .all()
    )
    for row in rows:
        meta = row.metadata_json if isinstance(row.metadata_json, dict) else {}
        if str(meta.get("snapshot_key") or "") != key:
            continue
        payload = meta.get("payload")
        if not isinstance(payload, dict):
            continue
        timestamp = _parse_snapshot_timestamp(meta.get("snapshot_timestamp"), row.fetched_at)
        age = _snapshot_age_minutes(timestamp)
        if age is None or age > max_age_minutes:
            continue
        return {
            "payload": payload,
            "snapshot_timestamp": _format_snapshot_timestamp(timestamp),
            "snapshot_age_minutes": age,
        }
    return None


def _benchmark_to_payload(benchmark: MarketBenchmarks) -> dict[str, Any]:
    return {
        "salary_avg": benchmark.salary_avg,
        "vacancy_index": benchmark.vacancy_index,
        "trend_label": benchmark.trend_label,
        "volatility_points": benchmark.volatility_points,
        "adzuna_query_mode": benchmark.adzuna_query_mode,
        "adzuna_query_used": benchmark.adzuna_query_used,
        "adzuna_location_used": benchmark.adzuna_location_used,
        "history_points_found": benchmark.history_points_found,
        "salary_points_found": benchmark.salary_points_found,
        "salary_percentile_local": benchmark.salary_percentile_local,
        "top_hiring_companies": benchmark.top_hiring_companies,
        "vacancy_growth_percent": benchmark.vacancy_growth_percent,
        "volatility_score": benchmark.volatility_score,
    }


def _benchmark_from_payload(payload: dict[str, Any]) -> MarketBenchmarks:
    return MarketBenchmarks(
        salary_avg=payload.get("salary_avg"),
        vacancy_index=float(payload.get("vacancy_index") or 0.0),
        trend_label=str(payload.get("trend_label") or "neutral"),
        volatility_points=payload.get("volatility_points") if isinstance(payload.get("volatility_points"), list) else [],
        adzuna_query_mode=str(payload.get("adzuna_query_mode") or "exact"),
        adzuna_query_used=str(payload.get("adzuna_query_used") or "") or None,
        adzuna_location_used=str(payload.get("adzuna_location_used") or "") or None,
        history_points_found=int(payload.get("history_points_found") or 0),
        salary_points_found=int(payload.get("salary_points_found") or 0),
        salary_percentile_local=payload.get("salary_percentile_local"),
        top_hiring_companies=payload.get("top_hiring_companies") if isinstance(payload.get("top_hiring_companies"), list) else [],
        vacancy_growth_percent=float(payload.get("vacancy_growth_percent") or 0.0),
        volatility_score=float(payload.get("volatility_score") or 0.0),
    )


def _pick_fallback_snapshot_meta(snapshot_meta: list[dict[str, Any]]) -> tuple[str | None, float | None]:
    if not snapshot_meta:
        return None, None
    selected = max(snapshot_meta, key=lambda item: float(item.get("snapshot_age_minutes") or 0.0))
    return selected.get("snapshot_timestamp"), selected.get("snapshot_age_minutes")


def _snapshot_stress_fallback(
    db: Session,
    *,
    target_job: str,
    location: str,
) -> dict[str, Any] | None:
    key = _snapshot_key(target_job, location)
    snapshot = _load_snapshot(
        db,
        source=SNAPSHOT_SOURCE_STRESS,
        key=key,
        max_age_hours=SNAPSHOT_TTL_STRESS_HOURS,
    )
    if not snapshot:
        return None

    payload = dict(snapshot.get("payload") or {})
    provider_status = payload.get("provider_status") if isinstance(payload.get("provider_status"), dict) else {}
    provider_status["adzuna"] = "snapshot_fallback"
    provider_status["careeronestop"] = "snapshot_fallback"
    payload["provider_status"] = provider_status
    payload["source_mode"] = "snapshot_fallback"
    payload["data_freshness"] = "snapshot_fallback"
    payload["snapshot_timestamp"] = snapshot.get("snapshot_timestamp")
    payload["snapshot_age_minutes"] = snapshot.get("snapshot_age_minutes")
    payload.setdefault("adzuna_query_mode", "exact")
    payload.setdefault("adzuna_query_used", None)
    payload.setdefault("adzuna_location_used", None)
    return payload


def _fetch_history_points(
    client: httpx.Client,
    *,
    base: str,
    country: str,
    what: str,
    where: str,
) -> list[dict[str, float]]:
    response = client.get(
        f"{base}/{country}/history",
        params={
            "app_id": settings.adzuna_app_id,
            "app_key": settings.adzuna_app_key,
            "what": what,
            "where": where,
            "months": 6,
        },
    )
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("month") or payload.get("results") or []

    points: list[dict[str, float]] = []
    if isinstance(rows, dict):
        for idx, (_, value) in enumerate(sorted(rows.items(), key=lambda item: item[0])):
            count = float(value or 0.0)
            points.append({"x": float(idx), "y": count})
    elif isinstance(rows, list):
        for idx, row in enumerate(rows):
            count = 0.0
            if isinstance(row, dict):
                count = float(row.get("count") or row.get("vacancies") or row.get("value") or 0)
            elif isinstance(row, (int, float)):
                count = float(row)
            points.append({"x": float(idx), "y": count})
    return points


def _fetch_search_count(
    client: httpx.Client,
    *,
    base: str,
    country: str,
    what: str,
    where: str,
    max_days_old: int,
) -> float:
    try:
        response = client.get(
            f"{base}/{country}/search/1",
            params={
                "app_id": settings.adzuna_app_id,
                "app_key": settings.adzuna_app_key,
                "what": what,
                "where": where,
                "results_per_page": 1,
                "max_days_old": max_days_old,
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            return 0.0
        return float(payload.get("count") or 0.0)
    except Exception:
        return 0.0


def _fetch_histogram_metrics(
    client: httpx.Client,
    *,
    base: str,
    country: str,
    what: str,
    where: str,
) -> tuple[float | None, int, float | None]:
    response = client.get(
        f"{base}/{country}/histogram",
        params={
            "app_id": settings.adzuna_app_id,
            "app_key": settings.adzuna_app_key,
            "what": what,
            "where": where,
        },
    )
    response.raise_for_status()
    payload = response.json()
    buckets = payload.get("salary_is_predicted") or payload.get("histogram") or payload.get("results") or {}
    if not isinstance(buckets, dict) or not buckets:
        return None, 0, None

    weighted_sum = 0.0
    total = 0.0
    distribution: list[tuple[float, float]] = []
    for key, value in buckets.items():
        try:
            salary = float(str(key).split("-")[0])
            cnt = float(value)
        except Exception:
            continue
        weighted_sum += salary * cnt
        total += cnt
        distribution.append((salary, cnt))

    if total <= 0:
        return None, 0, None

    salary_avg = weighted_sum / total
    cumulative = 0.0
    for salary, count in sorted(distribution, key=lambda row: row[0]):
        if salary <= salary_avg:
            cumulative += count
    salary_percentile_local = _clamp_score((cumulative / total) * 100.0)
    return salary_avg, int(total), salary_percentile_local


def _fetch_top_hiring_companies(
    client: httpx.Client,
    *,
    base: str,
    country: str,
    what: str,
    where: str,
) -> list[dict[str, Any]]:
    try:
        response = client.get(
            f"{base}/{country}/search/1",
            params={
                "app_id": settings.adzuna_app_id,
                "app_key": settings.adzuna_app_key,
                "what": what,
                "where": where,
                "results_per_page": 50,
                "sort_by": "date",
            },
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("results") if isinstance(payload, dict) else []
        if not isinstance(rows, list):
            return []

        company_counts: dict[str, int] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            company_block = row.get("company")
            company_name = ""
            if isinstance(company_block, dict):
                company_name = str(company_block.get("display_name") or "").strip()
            if not company_name:
                continue
            company_counts[company_name] = company_counts.get(company_name, 0) + 1

        return [
            {"name": name, "open_roles": count}
            for name, count in sorted(company_counts.items(), key=lambda item: item[1], reverse=True)[:5]
        ]
    except Exception:
        return []


def _compute_proxy_from_search(
    client: httpx.Client,
    *,
    base: str,
    country: str,
    what: str,
    where: str,
) -> dict[str, Any] | None:
    counts = [
        _fetch_search_count(
            client,
            base=base,
            country=country,
            what=what,
            where=where,
            max_days_old=days,
        )
        for days in ADZUNA_PROXY_WINDOWS
    ]
    if max(counts) <= 0:
        return None

    rates = [count / days for count, days in zip(counts, ADZUNA_PROXY_WINDOWS)]
    base_rate = max(rates[0], 0.1)
    recent_rate = rates[-1]

    vacancy_index = _clamp_score((recent_rate / base_rate) * 50.0)
    vacancy_growth_percent = ((recent_rate - base_rate) / base_rate) * 100.0

    mean = sum(rates) / len(rates)
    variance = sum((value - mean) ** 2 for value in rates) / len(rates)
    std_dev = variance ** 0.5
    volatility_score = _clamp_score((std_dev / max(mean, 0.1)) * 100.0)

    trend_label = "heating_up" if vacancy_index >= 60 else "cooling_down" if vacancy_index <= 40 else "neutral"
    points = [{"x": float(idx), "y": round(rate, 4)} for idx, rate in enumerate(rates)]
    return {
        "vacancy_index": round(vacancy_index, 2),
        "vacancy_growth_percent": round(vacancy_growth_percent, 2),
        "volatility_score": round(volatility_score, 2),
        "trend_label": trend_label,
        "volatility_points": points,
    }


def fetch_adzuna_benchmarks(target_job: str, location: str) -> MarketBenchmarks:
    if not settings.adzuna_app_id or not settings.adzuna_app_key:
        raise RuntimeError("Adzuna is not configured. Set ADZUNA_APP_ID and ADZUNA_APP_KEY.")

    what = (target_job or "software engineer").strip() or "software engineer"
    where = (location or "United States").strip() or "United States"
    country = settings.adzuna_country
    timeout = 12.0
    base = "https://api.adzuna.com/v1/api/jobs"

    salary_avg: float | None = None
    vacancy_index = 0.0
    volatility_points: list[dict[str, float]] = []
    history_points_found = 0
    salary_points_found = 0
    salary_percentile_local: float | None = None
    top_hiring_companies: list[dict[str, Any]] = []
    vacancy_growth_percent = 0.0
    volatility_score = 0.0
    adzuna_query_mode = "exact"
    adzuna_query_used = what
    adzuna_location_used = where

    role_candidates = _build_role_candidates(what)
    location_candidates = _build_location_candidates(where)
    exact_role = role_candidates[0]
    exact_location = location_candidates[0]
    widened_locations = location_candidates[1:]

    history_success = False

    with httpx.Client(timeout=timeout) as client:
        # 1) exact role + exact location
        try:
            points = _fetch_history_points(
                client,
                base=base,
                country=country,
                what=exact_role,
                where=exact_location,
            )
            if len(points) >= 2:
                history_success = True
                adzuna_query_mode = "exact"
                adzuna_query_used = exact_role
                adzuna_location_used = exact_location
                volatility_points = points
        except Exception:
            points = []

        # 2) rewritten roles + exact location
        if not history_success:
            for role in role_candidates[1:]:
                try:
                    points = _fetch_history_points(
                        client,
                        base=base,
                        country=country,
                        what=role,
                        where=exact_location,
                    )
                except Exception:
                    continue
                if len(points) >= 2:
                    history_success = True
                    adzuna_query_mode = "role_rewrite"
                    adzuna_query_used = role
                    adzuna_location_used = exact_location
                    volatility_points = points
                    break

        # 3) exact role + widened locations
        if not history_success:
            for widened_location in widened_locations:
                try:
                    points = _fetch_history_points(
                        client,
                        base=base,
                        country=country,
                        what=exact_role,
                        where=widened_location,
                    )
                except Exception:
                    continue
                if len(points) >= 2:
                    history_success = True
                    adzuna_query_mode = "geo_widen"
                    adzuna_query_used = exact_role
                    adzuna_location_used = widened_location
                    volatility_points = points
                    break

        # 4) rewritten roles + widened locations
        if not history_success:
            for role in role_candidates[1:]:
                found_in_loop = False
                for widened_location in widened_locations:
                    try:
                        points = _fetch_history_points(
                            client,
                            base=base,
                            country=country,
                            what=role,
                            where=widened_location,
                        )
                    except Exception:
                        continue
                    if len(points) >= 2:
                        history_success = True
                        found_in_loop = True
                        adzuna_query_mode = "geo_widen"
                        adzuna_query_used = role
                        adzuna_location_used = widened_location
                        volatility_points = points
                        break
                if found_in_loop:
                    break

        # 5) proxy from search windows for best live pair if history remains sparse
        if not history_success:
            best_role = ""
            best_location = ""
            best_count_30 = 0.0
            for role in role_candidates:
                for loc in location_candidates:
                    count_30 = _fetch_search_count(
                        client,
                        base=base,
                        country=country,
                        what=role,
                        where=loc,
                        max_days_old=30,
                    )
                    if count_30 > best_count_30:
                        best_count_30 = count_30
                        best_role = role
                        best_location = loc

            if best_count_30 <= 0.0 or not best_role or not best_location:
                raise RuntimeError("Adzuna benchmarks unavailable after role rewrite, geo widen, and proxy attempts.")

            proxy = _compute_proxy_from_search(
                client,
                base=base,
                country=country,
                what=best_role,
                where=best_location,
            )
            if not proxy:
                raise RuntimeError("Adzuna benchmarks unavailable after role rewrite, geo widen, and proxy attempts.")

            adzuna_query_mode = "proxy_from_search"
            adzuna_query_used = best_role
            adzuna_location_used = best_location
            vacancy_index = float(proxy["vacancy_index"])
            vacancy_growth_percent = float(proxy["vacancy_growth_percent"])
            volatility_score = float(proxy["volatility_score"])
            volatility_points = list(proxy["volatility_points"])
            trend_label = str(proxy["trend_label"])
            history_points_found = 0
        else:
            history_points_found = len(volatility_points)
            first = max(volatility_points[0]["y"], 1.0)
            last = volatility_points[-1]["y"]
            vacancy_index = _clamp_score((last / first) * 50.0)
            vacancy_growth_percent = ((last - first) / first) * 100.0

            series = [point["y"] for point in volatility_points if point["y"] > 0]
            if len(series) >= 2:
                mean = sum(series) / len(series)
                variance = sum((value - mean) ** 2 for value in series) / len(series)
                std_dev = variance ** 0.5
                volatility_score = _clamp_score((std_dev / max(mean, 1.0)) * 100.0)
            trend_label = "heating_up" if vacancy_index >= 60 else "cooling_down" if vacancy_index <= 40 else "neutral"

        try:
            salary_avg, salary_points_found, salary_percentile_local = _fetch_histogram_metrics(
                client,
                base=base,
                country=country,
                what=adzuna_query_used or what,
                where=adzuna_location_used or where,
            )
        except Exception:
            raise RuntimeError("Adzuna histogram endpoint failed or timed out.")

        top_hiring_companies = _fetch_top_hiring_companies(
            client,
            base=base,
            country=country,
            what=adzuna_query_used or what,
            where=adzuna_location_used or where,
        )

    if not volatility_points:
        raise RuntimeError("Adzuna benchmarks unavailable after role rewrite, geo widen, and proxy attempts.")

    return MarketBenchmarks(
        salary_avg=salary_avg,
        vacancy_index=round(vacancy_index, 2),
        trend_label=trend_label,
        volatility_points=volatility_points,
        adzuna_query_mode=adzuna_query_mode,
        adzuna_query_used=adzuna_query_used,
        adzuna_location_used=adzuna_location_used,
        history_points_found=history_points_found,
        salary_points_found=salary_points_found,
        salary_percentile_local=round(salary_percentile_local, 2) if salary_percentile_local is not None else None,
        top_hiring_companies=top_hiring_companies,
        vacancy_growth_percent=round(vacancy_growth_percent, 2),
        volatility_score=round(volatility_score, 2),
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
    snapshot_meta: list[dict[str, Any]] = []
    key = _snapshot_key(target_job, location)

    try:
        required_skills = fetch_careeronestop_skills(target_job)
        try:
            _save_snapshot(
                db,
                source=SNAPSHOT_SOURCE_SKILLS,
                key=key,
                payload={"required_skills": required_skills},
            )
        except Exception:
            db.rollback()
    except RuntimeError as live_error:
        skills_snapshot = _load_snapshot(
            db,
            source=SNAPSHOT_SOURCE_SKILLS,
            key=key,
            max_age_hours=SNAPSHOT_TTL_SKILLS_HOURS,
        )
        if not skills_snapshot:
            stress_snapshot = _snapshot_stress_fallback(db, target_job=target_job, location=location)
            if stress_snapshot:
                return stress_snapshot
            raise live_error
        payload = skills_snapshot.get("payload") if isinstance(skills_snapshot.get("payload"), dict) else {}
        required_skills = payload.get("required_skills") if isinstance(payload.get("required_skills"), list) else []
        if not required_skills:
            stress_snapshot = _snapshot_stress_fallback(db, target_job=target_job, location=location)
            if stress_snapshot:
                return stress_snapshot
            raise live_error
        provider_status["careeronestop"] = "snapshot_fallback"
        snapshot_meta.append(skills_snapshot)

    try:
        benchmarks = fetch_adzuna_benchmarks(target_job, location)
        try:
            _save_snapshot(
                db,
                source=SNAPSHOT_SOURCE_ADZUNA,
                key=key,
                payload=_benchmark_to_payload(benchmarks),
            )
        except Exception:
            db.rollback()
    except RuntimeError as live_error:
        adzuna_snapshot = _load_snapshot(
            db,
            source=SNAPSHOT_SOURCE_ADZUNA,
            key=key,
            max_age_hours=SNAPSHOT_TTL_ADZUNA_HOURS,
        )
        if not adzuna_snapshot:
            stress_snapshot = _snapshot_stress_fallback(db, target_job=target_job, location=location)
            if stress_snapshot:
                return stress_snapshot
            raise live_error
        payload = adzuna_snapshot.get("payload") if isinstance(adzuna_snapshot.get("payload"), dict) else {}
        benchmarks = _benchmark_from_payload(payload)
        provider_status["adzuna"] = "snapshot_fallback"
        snapshot_meta.append(adzuna_snapshot)

    verified_skill_names = _load_verified_skill_names(db, user_id)

    if required_skills:
        overlap_count = len({skill for skill in required_skills if skill in verified_skill_names})
        skill_overlap_score = _clamp_score((overlap_count / len(required_skills)) * 100.0)
    else:
        overlap_count = 0
        skill_overlap_score = 0.0

    evidence_score, evidence_counts = _evidence_verification_score(db, user_id)
    evidence_score = _clamp_score(evidence_score)
    market_trend_score = _clamp_score(benchmarks.vacancy_index)
    salary_momentum = 50.0
    if benchmarks.salary_avg and benchmarks.salary_avg > 0:
        salary_momentum = 55.0 if benchmarks.salary_avg >= 60000 else 45.0

    slope_component = 100.0 if benchmarks.trend_label == "heating_up" else 20.0 if benchmarks.trend_label == "cooling_down" else 55.0
    job_stability_score_2027 = round(
        _clamp_score((0.7 * market_trend_score) + (0.3 * ((salary_momentum + slope_component) / 2.0))),
        2,
    )

    final_score = (0.40 * skill_overlap_score) + (0.30 * market_trend_score) + (0.30 * evidence_score)
    final_score = round(_clamp_score(final_score), 2)
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

    source_mode = "snapshot_fallback" if snapshot_meta else "live"
    snapshot_timestamp, snapshot_age_minutes = _pick_fallback_snapshot_meta(snapshot_meta)

    result = {
        "score": final_score,
        "mri_formula": MRI_FORMULA,
        "mri_formula_version": MRI_FORMULA_VERSION,
        "computed_at": _format_snapshot_timestamp(_utcnow()),
        "components": {
            "skill_overlap_score": round(skill_overlap_score, 2),
            "evidence_verification_score": round(evidence_score, 2),
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
        "salary_percentile_local": benchmarks.salary_percentile_local,
        "top_hiring_companies": benchmarks.top_hiring_companies,
        "vacancy_growth_percent": benchmarks.vacancy_growth_percent,
        "market_volatility_score": _clamp_score(benchmarks.volatility_score),
        "adzuna_query_mode": benchmarks.adzuna_query_mode,
        "adzuna_query_used": benchmarks.adzuna_query_used,
        "adzuna_location_used": benchmarks.adzuna_location_used,
        "vacancy_trend_label": benchmarks.trend_label,
        "job_stability_score_2027": job_stability_score_2027,
        "data_freshness": source_mode,
        "source_mode": source_mode,
        "snapshot_timestamp": snapshot_timestamp,
        "snapshot_age_minutes": snapshot_age_minutes,
        "provider_status": provider_status,
        "market_volatility_points": benchmarks.volatility_points,
        "evidence_counts": evidence_counts,
        "simulation_2027": simulation_2027,
        "citations": citations,
    }

    if source_mode == "live":
        try:
            _save_snapshot(
                db,
                source=SNAPSHOT_SOURCE_STRESS,
                key=key,
                payload=result,
            )
        except Exception:
            db.rollback()

    return result


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
    key = _snapshot_key(target_job, location)
    snapshot_meta: list[dict[str, Any]] = []

    try:
        required_skills = fetch_careeronestop_skills(target_job)
        try:
            _save_snapshot(
                db,
                source=SNAPSHOT_SOURCE_SKILLS,
                key=key,
                payload={"required_skills": required_skills},
            )
        except Exception:
            db.rollback()
    except RuntimeError as live_error:
        skills_snapshot = _load_snapshot(
            db,
            source=SNAPSHOT_SOURCE_SKILLS,
            key=key,
            max_age_hours=SNAPSHOT_TTL_SKILLS_HOURS,
        )
        if not skills_snapshot:
            raise live_error
        payload = skills_snapshot.get("payload") if isinstance(skills_snapshot.get("payload"), dict) else {}
        required_skills = payload.get("required_skills") if isinstance(payload.get("required_skills"), list) else []
        if not required_skills:
            raise live_error
        snapshot_meta.append(skills_snapshot)

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

    try:
        benchmark = fetch_adzuna_benchmarks(target_job, location)
        try:
            _save_snapshot(
                db,
                source=SNAPSHOT_SOURCE_ADZUNA,
                key=key,
                payload=_benchmark_to_payload(benchmark),
            )
        except Exception:
            db.rollback()
    except RuntimeError as live_error:
        adzuna_snapshot = _load_snapshot(
            db,
            source=SNAPSHOT_SOURCE_ADZUNA,
            key=key,
            max_age_hours=SNAPSHOT_TTL_ADZUNA_HOURS,
        )
        if not adzuna_snapshot:
            raise live_error
        payload = adzuna_snapshot.get("payload") if isinstance(adzuna_snapshot.get("payload"), dict) else {}
        benchmark = _benchmark_from_payload(payload)
        snapshot_meta.append(adzuna_snapshot)

    source_mode = "snapshot_fallback" if snapshot_meta else "live"
    snapshot_timestamp, snapshot_age_minutes = _pick_fallback_snapshot_meta(snapshot_meta)
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
        "adzuna_query_mode": benchmark.adzuna_query_mode,
        "adzuna_query_used": benchmark.adzuna_query_used,
        "adzuna_location_used": benchmark.adzuna_location_used,
        "source_mode": source_mode,
        "snapshot_timestamp": snapshot_timestamp,
        "snapshot_age_minutes": snapshot_age_minutes,
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
