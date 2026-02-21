"""GitHub Signal Auditor - analyzes a user's GitHub repos to verify skills and contribution velocity."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException

GITHUB_API_BASE = "https://api.github.com"
REQUEST_TIMEOUT = 10.0
RECENT_WINDOW_DAYS = 90
HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "MarketReadySignalAuditor/1.0",
}

# Dependency -> skill mappings
DEP_SKILL_MAP: dict[str, list[str]] = {
    "react": ["React", "Frontend"],
    "next": ["Next.js", "React"],
    "vue": ["Vue.js", "Frontend"],
    "angular": ["Angular", "Frontend"],
    "express": ["Node.js", "Backend"],
    "fastapi": ["FastAPI", "Python", "Backend"],
    "django": ["Django", "Python", "Backend"],
    "flask": ["Flask", "Python", "Backend"],
    "sqlalchemy": ["SQL", "Database"],
    "prisma": ["Database", "SQL"],
    "mongoose": ["MongoDB", "Database"],
    "postgres": ["PostgreSQL", "Database"],
    "redis": ["Redis", "Database"],
    "boto3": ["AWS", "Cloud"],
    "docker": ["Docker", "DevOps"],
    "kubernetes": ["Kubernetes", "DevOps"],
    "tensorflow": ["Machine Learning", "Python"],
    "torch": ["Machine Learning", "Python"],
    "sklearn": ["Machine Learning", "Python"],
    "numpy": ["Python", "Data Analysis"],
    "pandas": ["Python", "Data Analysis"],
    "stripe": ["Payments", "API"],
    "tailwind": ["Tailwind CSS", "Frontend"],
    "typescript": ["TypeScript", "Frontend"],
}

COMMIT_SKILL_KEYWORDS = {
    "fix": [],
    "feat": [],
    "api": ["API Development"],
    "auth": ["Authentication"],
    "deploy": ["Deployment", "DevOps"],
    "docker": ["Docker"],
    "test": ["Testing"],
    "db": ["Database"],
    "sql": ["SQL"],
    "ci": ["CI/CD"],
    "ml": ["Machine Learning"],
    "data": ["Data Analysis"],
    "react": ["React"],
    "python": ["Python"],
    "aws": ["AWS"],
}

router = APIRouter(prefix="/github")


def _fetch_repos(client: httpx.Client, username: str) -> list[dict]:
    resp = client.get(
        f"{GITHUB_API_BASE}/users/{username}/repos",
        params={"per_page": 30, "sort": "updated", "type": "owner"},
    )
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=f"GitHub user '{username}' not found")
    if resp.status_code == 403:
        return []
    resp.raise_for_status()
    return resp.json() if isinstance(resp.json(), list) else []


def _fetch_package_json(client: httpx.Client, owner: str, repo: str) -> dict | None:
    try:
        resp = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/package.json")
        if resp.status_code != 200:
            return None
        import base64 as b64, json as _json2
        content_b64 = resp.json().get("content", "")
        content = b64.b64decode(content_b64.replace("\n", "")).decode("utf-8")
        return _json2.loads(content)
    except Exception:
        return None


def _fetch_requirements_txt(client: httpx.Client, owner: str, repo: str) -> list[str]:
    try:
        resp = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/requirements.txt")
        if resp.status_code != 200:
            return []
        import base64
        content_b64 = resp.json().get("content", "")
        content = base64.b64decode(content_b64.replace("\n", "")).decode("utf-8")
        return [line.split("==")[0].split(">=")[0].strip().lower() for line in content.splitlines() if line.strip() and not line.startswith("#")]
    except Exception:
        return []


def _fetch_recent_commits(client: httpx.Client, owner: str, repo: str) -> list[dict]:
    try:
        since = (datetime.now(timezone.utc) - timedelta(days=RECENT_WINDOW_DAYS)).isoformat()
        resp = client.get(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits",
            params={"per_page": 30, "since": since},
        )
        if resp.status_code != 200:
            return []
        return resp.json() if isinstance(resp.json(), list) else []
    except Exception:
        return []


def _extract_skills_from_deps(deps: list[str]) -> set[str]:
    skills: set[str] = set()
    for dep in deps:
        dep_lower = dep.lower().strip()
        for keyword, mapped in DEP_SKILL_MAP.items():
            if keyword in dep_lower:
                skills.update(mapped)
    return skills


def _extract_skills_from_commits(commits: list[dict]) -> set[str]:
    skills: set[str] = set()
    for commit in commits:
        msg = (commit.get("commit", {}).get("message") or "").lower()
        for keyword, mapped in COMMIT_SKILL_KEYWORDS.items():
            if keyword in msg:
                skills.update(mapped)
    return skills


def _check_bulk_upload(repos: list[dict]) -> bool:
    """Detect if repos were bulk-created (many repos on same day)."""
    if len(repos) < 5:
        return False
    dates: dict[str, int] = {}
    for repo in repos:
        created = str(repo.get("created_at", ""))[:10]
        dates[created] = dates.get(created, 0) + 1
    return any(count >= 5 for count in dates.values())


def _compute_velocity(repos: list[dict], total_commits: int) -> dict:
    now = datetime.now(timezone.utc)
    recent_threshold = now - timedelta(days=RECENT_WINDOW_DAYS)
    recent_repos = [
        r for r in repos
        if r.get("pushed_at") and datetime.fromisoformat(r["pushed_at"].replace("Z", "+00:00")) >= recent_threshold
    ]
    stars = sum(int(r.get("stargazers_count") or 0) for r in repos)
    languages: set[str] = set()
    for r in repos:
        lang = (r.get("language") or "").strip()
        if lang:
            languages.add(lang)

    velocity_score = min(100, (
        min(len(recent_repos), 10) / 10 * 40 +
        min(total_commits, 100) / 100 * 40 +
        min(len(languages), 5) / 5 * 20
    ))

    return {
        "recent_repos": len(recent_repos),
        "total_repos": len(repos),
        "total_commits_sampled": total_commits,
        "languages": sorted(languages),
        "stars": stars,
        "velocity_score": round(velocity_score, 1),
    }


@router.get("/audit/{username}")
def audit_github_user(username: str) -> dict[str, Any]:
    """Analyze a GitHub user's repositories for skills and contribution velocity."""
    if not username or not re.match(r"^[a-zA-Z0-9\-]{1,39}$", username):
        raise HTTPException(status_code=400, detail="Invalid GitHub username")

    verified_skills: set[str] = set()
    commit_skill_signals: set[str] = set()
    total_commits = 0
    warnings: list[str] = []

    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT, headers=HEADERS, follow_redirects=True) as client:
            # Fetch user info
            user_resp = client.get(f"{GITHUB_API_BASE}/users/{username}")
            if user_resp.status_code == 404:
                raise HTTPException(status_code=404, detail=f"GitHub user '{username}' not found")
            user_data = user_resp.json() if user_resp.status_code == 200 else {}

            repos = _fetch_repos(client, username)
            if not repos:
                return {
                    "username": username,
                    "verified_skills": [],
                    "commit_skill_signals": [],
                    "velocity": {"velocity_score": 0, "recent_repos": 0, "total_repos": 0, "total_commits_sampled": 0, "languages": [], "stars": 0},
                    "warnings": ["No public repositories found"],
                    "bulk_upload_detected": False,
                    "profile": {"public_repos": 0, "followers": 0, "bio": None},
                }

            bulk_flag = _check_bulk_upload(repos)
            if bulk_flag:
                warnings.append("Bulk repo upload pattern detected — skills may be unverified")

            # Analyze top 5 repos for dependencies
            for repo in repos[:5]:
                repo_name = repo.get("name", "")
                owner = repo.get("owner", {}).get("login", username)
                lang = (repo.get("language") or "").strip()
                if lang:
                    verified_skills.add(lang)

                # Check package.json
                pkg = _fetch_package_json(client, owner, repo_name)
                if pkg:
                    deps = list(pkg.get("dependencies", {}).keys()) + list(pkg.get("devDependencies", {}).keys())
                    verified_skills.update(_extract_skills_from_deps(deps))

                # Check requirements.txt
                reqs = _fetch_requirements_txt(client, owner, repo_name)
                if reqs:
                    verified_skills.update(_extract_skills_from_deps(reqs))

                # Fetch recent commits
                commits = _fetch_recent_commits(client, owner, repo_name)
                total_commits += len(commits)
                commit_skill_signals.update(_extract_skills_from_commits(commits))

            velocity = _compute_velocity(repos, total_commits)

            # Language-to-skill mapping
            LANG_SKILLS = {
                "Python": "Python",
                "JavaScript": "JavaScript",
                "TypeScript": "TypeScript",
                "Java": "Java",
                "Go": "Go",
                "Rust": "Rust",
                "C#": "C#",
                "SQL": "SQL",
            }
            for lang, skill in LANG_SKILLS.items():
                if lang in verified_skills:
                    verified_skills.add(skill)

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GitHub API error: {str(exc)[:200]}")

    return {
        "username": username,
        "verified_skills": sorted(verified_skills),
        "commit_skill_signals": sorted(commit_skill_signals),
        "velocity": velocity,
        "warnings": warnings,
        "bulk_upload_detected": bulk_flag if repos else False,
        "profile": {
            "public_repos": int(user_data.get("public_repos") or 0),
            "followers": int(user_data.get("followers") or 0),
            "bio": user_data.get("bio"),
        },
    }
