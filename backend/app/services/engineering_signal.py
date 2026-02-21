from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import log1p
from threading import Lock
import time
from typing import Any

import httpx

GITHUB_API_BASE = "https://api.github.com"
REQUEST_TIMEOUT_SECONDS = 3.0
RECENT_WINDOW_DAYS = 90
README_SAMPLE_LIMIT = 10
CACHE_TTL_SECONDS = 15 * 60

_cache_lock = Lock()
_signal_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _default_payload() -> dict[str, Any]:
    return {
        "score": 0.0,
        "metrics": {
            "public_repos": 0,
            "recent_repo_count": 0,
            "total_stars": 0,
            "unique_languages": 0,
            "readme_presence_ratio": 0.0,
        },
    }


def _cache_get(username: str) -> dict[str, Any] | None:
    now = time.time()
    with _cache_lock:
        row = _signal_cache.get(username)
        if not row:
            return None
        expires_at, payload = row
        if now > expires_at:
            _signal_cache.pop(username, None)
            return None
        return payload


def _cache_set(username: str, payload: dict[str, Any]) -> None:
    expires_at = time.time() + CACHE_TTL_SECONDS
    with _cache_lock:
        _signal_cache[username] = (expires_at, payload)
        if len(_signal_cache) > 1024:
            oldest = min(_signal_cache.items(), key=lambda item: item[1][0])[0]
            _signal_cache.pop(oldest, None)


def _safe_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _readme_ratio(client: httpx.Client, owner: str, repos: list[dict[str, Any]]) -> float:
    sample = repos[:README_SAMPLE_LIMIT]
    if not sample:
        return 0.0

    found = 0
    checked = 0
    for repo in sample:
        name = str(repo.get("name") or "").strip()
        if not name:
            continue
        checked += 1
        try:
            response = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{name}/readme")
        except Exception:
            continue

        if response.status_code == 200:
            found += 1
            continue

        # Rate-limit and abuse-prevention responses. Stop and use checked sample.
        if response.status_code in {403, 429}:
            break

    if checked <= 0:
        return 0.0
    return round(found / checked, 3)


def _compute_score(
    *,
    public_repos: int,
    recent_repo_count: int,
    total_stars: int,
    unique_languages: int,
    readme_presence_ratio: float,
) -> float:
    repo_component = min(public_repos, 30) / 30 * 25
    recent_component = min(recent_repo_count, 20) / 20 * 25
    star_component = min(log1p(max(total_stars, 0)) / log1p(200), 1.0) * 20
    language_component = min(unique_languages, 10) / 10 * 15
    readme_component = min(max(readme_presence_ratio, 0.0), 1.0) * 15
    return round(min(max(repo_component + recent_component + star_component + language_component + readme_component, 0.0), 100.0), 1)


def compute_engineering_signal(github_username: str) -> dict[str, Any]:
    username = (github_username or "").strip().lower()
    if not username:
        return _default_payload()

    cached = _cache_get(username)
    if cached is not None:
        return cached

    fallback = _default_payload()
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "MarketReadyEngineeringSignal/1.0",
    }

    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS, headers=headers, follow_redirects=True) as client:
            user_response = client.get(f"{GITHUB_API_BASE}/users/{username}")
            if user_response.status_code != 200:
                _cache_set(username, fallback)
                return fallback
            user_payload = user_response.json()
            user_data = user_payload if isinstance(user_payload, dict) else {}

            repos_response = client.get(
                f"{GITHUB_API_BASE}/users/{username}/repos",
                params={"per_page": 100, "sort": "updated", "direction": "desc", "type": "owner"},
            )
            if repos_response.status_code != 200:
                _cache_set(username, fallback)
                return fallback
            repos = repos_response.json()
            if not isinstance(repos, list):
                _cache_set(username, fallback)
                return fallback

            now = datetime.now(timezone.utc)
            recent_threshold = now - timedelta(days=RECENT_WINDOW_DAYS)

            public_repos = int(user_data.get("public_repos") or len(repos) or 0)
            recent_repo_count = 0
            total_stars = 0
            languages: set[str] = set()

            for repo in repos:
                if not isinstance(repo, dict):
                    continue
                updated_at = _safe_dt(repo.get("updated_at"))
                if updated_at and updated_at >= recent_threshold:
                    recent_repo_count += 1
                total_stars += int(repo.get("stargazers_count") or 0)
                language = (repo.get("language") or "").strip()
                if language:
                    languages.add(language.lower())

            readme_presence_ratio = _readme_ratio(client, username, repos)
            unique_languages = len(languages)
            score = _compute_score(
                public_repos=public_repos,
                recent_repo_count=recent_repo_count,
                total_stars=total_stars,
                unique_languages=unique_languages,
                readme_presence_ratio=readme_presence_ratio,
            )

            payload = {
                "score": score,
                "metrics": {
                    "public_repos": public_repos,
                    "recent_repo_count": recent_repo_count,
                    "total_stars": total_stars,
                    "unique_languages": unique_languages,
                    "readme_presence_ratio": readme_presence_ratio,
                },
            }
            _cache_set(username, payload)
            return payload
    except Exception:
        _cache_set(username, fallback)
        return fallback
