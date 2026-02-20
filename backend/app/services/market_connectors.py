from __future__ import annotations

from datetime import datetime
import re
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import settings


def _extract_skill_tokens(text: str) -> list[str]:
    if not text:
        return []
    normalized = text.lower()
    curated = [
        "python",
        "sql",
        "java",
        "javascript",
        "react",
        "aws",
        "docker",
        "kubernetes",
        "power bi",
        "tableau",
        "machine learning",
        "data analysis",
        "api",
        "full stack",
        "cybersecurity",
    ]
    found = []
    for skill in curated:
        if skill in normalized:
            found.append(skill)
    if found:
        return found

    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_+.-]{2,}", text)
    return list(dict.fromkeys(words[:8]))


def _to_signal_rows(
    *,
    provider: str,
    records: list[dict[str, Any]],
    pathway_id: str | None,
    role_family: str | None,
) -> list[dict[str, Any]]:
    now = datetime.utcnow()
    counts: dict[str, int] = {}
    for record in records:
        title = str(record.get("title") or "")
        description = str(record.get("description") or "")
        combined = f"{title} {description}"
        for token in _extract_skill_tokens(combined):
            key = token.strip().lower()
            if not key:
                continue
            counts[key] = counts.get(key, 0) + 1

    rows: list[dict[str, Any]] = []
    total = max(sum(counts.values()), 1)
    for skill, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:25]:
        rows.append(
            {
                "pathway_id": pathway_id,
                "skill_name": skill,
                "role_family": role_family,
                "window_start": None,
                "window_end": now,
                "frequency": round(count / total, 4),
                "source_count": count,
                "metadata": {
                    "provider": provider,
                    "record_count": len(records),
                },
            }
        )
    return rows


def fetch_adzuna_jobs(
    *,
    query: str,
    limit: int = 25,
    role_family: str | None = None,
    pathway_id: str | None = None,
) -> list[dict[str, Any]]:
    if not settings.adzuna_app_id or not settings.adzuna_app_key:
        raise RuntimeError("Adzuna credentials are not configured")
    query_text = query.strip() or "software engineer"
    url = f"https://api.adzuna.com/v1/api/jobs/{settings.adzuna_country}/search/1"
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.get(
                url,
                params={
                    "app_id": settings.adzuna_app_id,
                    "app_key": settings.adzuna_app_key,
                    "results_per_page": max(1, min(limit, 50)),
                    "what": query_text,
                },
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Adzuna request failed: {exc}") from exc
    records = data.get("results") or []
    normalized = [
        {
            "title": row.get("title"),
            "description": row.get("description"),
            "company": (row.get("company") or {}).get("display_name"),
        }
        for row in records
    ]
    return _to_signal_rows(
        provider="adzuna",
        records=normalized,
        pathway_id=pathway_id,
        role_family=role_family,
    )


def fetch_onet_signals(
    *,
    query: str,
    limit: int = 25,
    role_family: str | None = None,
    pathway_id: str | None = None,
) -> list[dict[str, Any]]:
    if not settings.onet_username and not settings.onet_password:
        raise RuntimeError("O*NET credentials are not configured")
    keyword = query or "software"
    normalized: list[dict[str, Any]] = []

    api_key = (settings.onet_password or "").strip() or (settings.onet_username or "").strip()
    if api_key:
        try:
            with httpx.Client(timeout=20.0) as client:
                response = client.get(
                    "https://api-v2.onetcenter.org/mnm/search",
                    params={"keyword": keyword, "start": 1, "end": max(1, min(limit, 50))},
                    headers={"X-API-Key": api_key},
                )
                response.raise_for_status()
                data = response.json()
            rows = data.get("career") or []
            normalized = [
                {
                    "title": row.get("title") or "",
                    "description": "",
                }
                for row in rows[:50]
            ]
        except httpx.HTTPError:
            normalized = []

    if not normalized and settings.onet_username and settings.onet_password:
        try:
            with httpx.Client(timeout=20.0, auth=(settings.onet_username, settings.onet_password)) as client:
                response = client.get("https://services.onetcenter.org/ws/mnm/skills", params={"keyword": keyword})
                response.raise_for_status()
                data = response.json()
            rows = data.get("skills") or data.get("skill") or []
            normalized = [
                {
                    "title": row.get("title") or row.get("name") or "",
                    "description": row.get("description") or "",
                }
                for row in rows[:50]
            ]
        except httpx.HTTPError as exc:
            raise RuntimeError(f"O*NET request failed: {exc}") from exc

    if not normalized:
        raise RuntimeError("O*NET request failed: no records returned (check API key/credentials)")

    return _to_signal_rows(
        provider="onet",
        records=normalized,
        pathway_id=pathway_id,
        role_family=role_family,
    )


def fetch_careeronestop_signals(
    *,
    query: str,
    role_family: str | None = None,
    pathway_id: str | None = None,
) -> list[dict[str, Any]]:
    if not settings.careeronestop_api_key or not settings.careeronestop_user_id:
        raise RuntimeError("CareerOneStop credentials are not configured")
    query_segment = quote(query or "software developer", safe="")
    url = (
        f"https://api.careeronestop.org/v1/occupation/{settings.careeronestop_user_id}/"
        f"{query_segment}/US/0/10"
    )
    headers = {"Authorization": f"Bearer {settings.careeronestop_api_key}"}
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"CareerOneStop request failed: {exc}") from exc
    rows = (
        data.get("OccupationDetailList")
        or data.get("OccupationList")
        or data.get("Occupations")
        or data.get("occupationList")
        or []
    )
    normalized = [
        {
            "title": row.get("OnetTitle") or row.get("Title") or row.get("Occupation") or "",
            "description": row.get("OccupationDescription") or row.get("Duties") or row.get("BrightOutlook") or row.get("Description") or "",
        }
        for row in rows[:50]
    ]
    return _to_signal_rows(
        provider="careeronestop",
        records=normalized,
        pathway_id=pathway_id,
        role_family=role_family,
    )


def fetch_external_signals(
    *,
    provider: str,
    query: str,
    limit: int,
    pathway_id: str | None,
    role_family: str | None,
) -> list[dict[str, Any]]:
    normalized_provider = provider.strip().lower()
    if normalized_provider == "adzuna":
        return fetch_adzuna_jobs(
            query=query,
            limit=limit,
            pathway_id=pathway_id,
            role_family=role_family,
        )
    if normalized_provider == "onet":
        return fetch_onet_signals(
            query=query,
            limit=limit,
            pathway_id=pathway_id,
            role_family=role_family,
        )
    if normalized_provider == "careeronestop":
        return fetch_careeronestop_signals(
            query=query,
            pathway_id=pathway_id,
            role_family=role_family,
        )
    raise RuntimeError("Unsupported provider. Use one of: adzuna, onet, careeronestop")
