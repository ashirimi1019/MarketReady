from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import MarketSignal, Skill, StudentProfile
from app.services.ai import (
    _call_llm,
    _log_ai_audit,
    _safe_json,
    _truncate,
    ai_is_configured,
    ai_strict_mode_enabled,
    get_active_ai_model,
)


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        item = str(value).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _safe_list(value: Any, *, max_items: int = 6) -> list[str]:
    if not isinstance(value, list):
        return []
    return _unique([str(item) for item in value])[:max_items]


def _safe_optional_text(value: Any, *, max_chars: int = 600) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
    elif isinstance(value, (int, float, bool)):
        text = str(value)
    else:
        try:
            text = json.dumps(value, ensure_ascii=False)
        except Exception:
            text = str(value)
    text = text.strip()
    if not text:
        return None
    return text[:max_chars]


def _raise_if_ai_strict(reason: str) -> None:
    if ai_strict_mode_enabled():
        raise RuntimeError(reason)


def _market_snapshot(db: Session, *, role_hint: str | None = None, limit: int = 80) -> dict[str, Any]:
    query = db.query(MarketSignal, Skill).outerjoin(Skill, MarketSignal.skill_id == Skill.id)
    hint = (role_hint or "").strip().lower()
    if hint:
        query = query.filter(MarketSignal.role_family.ilike(f"%{hint}%"))
    rows = (
        query.order_by(MarketSignal.window_end.desc().nullslast(), MarketSignal.id.desc())
        .limit(max(10, min(limit, 200)))
        .all()
    )
    if not rows:
        return {"signal_count": 0, "top_skills": [], "top_roles": []}

    skill_counts: dict[str, int] = {}
    role_counts: dict[str, int] = {}
    for signal, skill in rows:
        label = ((skill.name if skill else None) or "").strip().lower()
        if label:
            skill_counts[label] = skill_counts.get(label, 0) + max(signal.source_count or 1, 1)
        role = (signal.role_family or "").strip().lower()
        if role:
            role_counts[role] = role_counts.get(role, 0) + max(signal.source_count or 1, 1)

    top_skills = [name for name, _ in sorted(skill_counts.items(), key=lambda row: row[1], reverse=True)[:8]]
    top_roles = [name for name, _ in sorted(role_counts.items(), key=lambda row: row[1], reverse=True)[:6]]
    return {
        "signal_count": len(rows),
        "top_skills": top_skills,
        "top_roles": top_roles,
    }


def _role_track(*parts: str | None) -> str:
    text = " ".join(part or "" for part in parts).lower()
    if any(token in text for token in ["html", "css", "frontend", "front-end", "react", "web", "ui", "ux"]):
        return "frontend"
    if any(token in text for token in ["data", "sql", "analytics", "bi", "tableau", "power bi", "ml"]):
        return "data"
    if any(token in text for token in ["security", "cyber", "soc", "siem", "threat", "iam"]):
        return "security"
    if any(token in text for token in ["backend", "api", "python", "java", "node", "cloud", "database"]):
        return "backend"
    return "general"


def _has_internship(history: str | None) -> bool:
    text = (history or "").strip().lower()
    if not text:
        return False
    if any(token in text for token in ["no internship", "none", "not yet", "without internship"]):
        return False
    return any(token in text for token in ["internship", "co-op", "co op", "apprenticeship", "interned"])


def _certs_for_track(track: str) -> list[str]:
    certs = {
        "frontend": [
            "freeCodeCamp - Responsive Web Design",
            "freeCodeCamp - JavaScript Algorithms and Data Structures",
            "Meta Front-End Developer Professional Certificate",
        ],
        "backend": [
            "Postman API Fundamentals Student Expert",
            "GitHub Foundations",
            "AWS Certified Developer - Associate",
        ],
        "data": [
            "Google Data Analytics Professional Certificate",
            "Microsoft Power BI Data Analyst (PL-300)",
            "Databricks Data Engineer Associate",
        ],
        "security": [
            "ISC2 Certified in Cybersecurity (CC)",
            "CompTIA Security+",
            "SC-900 Microsoft Security Fundamentals",
        ],
        "general": [
            "Google Career Certificate (role-aligned)",
            "AWS Certified Cloud Practitioner",
            "LinkedIn Learning + Portfolio Sprint",
        ],
    }
    return certs.get(track, certs["general"])[:5]


def _fallback_cert_roi_options(track: str) -> list[dict[str, Any]]:
    options = {
        "frontend": [
            {
                "certificate": "freeCodeCamp - JavaScript Algorithms and Data Structures",
                "cost_usd": "0",
                "time_required": "5-8 weeks",
                "entry_salary_range": "$60k-$100k",
                "difficulty_level": "Beginner-Intermediate",
                "demand_trend": "High",
                "roi_score": 94,
                "why_it_helps": "Strong signal for interactive web projects and junior frontend hiring.",
            },
            {
                "certificate": "Meta Front-End Developer Professional Certificate",
                "cost_usd": "$39-$59/month",
                "time_required": "8-16 weeks",
                "entry_salary_range": "$65k-$110k",
                "difficulty_level": "Intermediate",
                "demand_trend": "High",
                "roi_score": 86,
                "why_it_helps": "Structured pathway with portfolio outputs recruiters can review.",
            },
            {
                "certificate": "freeCodeCamp - Responsive Web Design",
                "cost_usd": "0",
                "time_required": "4-6 weeks",
                "entry_salary_range": "$55k-$90k",
                "difficulty_level": "Beginner",
                "demand_trend": "High",
                "roi_score": 91,
                "why_it_helps": "Fast validation for HTML/CSS and responsive UI readiness.",
            },
        ],
        "backend": [
            {
                "certificate": "Postman API Fundamentals Student Expert",
                "cost_usd": "0",
                "time_required": "2-4 weeks",
                "entry_salary_range": "$70k-$115k",
                "difficulty_level": "Beginner-Intermediate",
                "demand_trend": "High",
                "roi_score": 88,
                "why_it_helps": "Directly maps to API workflow expectations in backend roles.",
            },
            {
                "certificate": "AWS Certified Developer - Associate",
                "cost_usd": "$150 exam",
                "time_required": "8-12 weeks",
                "entry_salary_range": "$80k-$130k",
                "difficulty_level": "Intermediate",
                "demand_trend": "High",
                "roi_score": 84,
                "why_it_helps": "Cloud deployment credential commonly seen in backend postings.",
            },
            {
                "certificate": "GitHub Foundations",
                "cost_usd": "$99 exam",
                "time_required": "2-4 weeks",
                "entry_salary_range": "$65k-$105k",
                "difficulty_level": "Beginner",
                "demand_trend": "High",
                "roi_score": 83,
                "why_it_helps": "Improves collaboration signal and repository quality for hiring reviews.",
            },
        ],
        "data": [
            {
                "certificate": "Google Data Analytics Professional Certificate",
                "cost_usd": "$39-$59/month",
                "time_required": "8-16 weeks",
                "entry_salary_range": "$60k-$95k",
                "difficulty_level": "Beginner-Intermediate",
                "demand_trend": "High",
                "roi_score": 89,
                "why_it_helps": "Foundational data skill coverage with portfolio-friendly output.",
            },
            {
                "certificate": "Microsoft Power BI Data Analyst (PL-300)",
                "cost_usd": "$165 exam",
                "time_required": "6-10 weeks",
                "entry_salary_range": "$65k-$105k",
                "difficulty_level": "Intermediate",
                "demand_trend": "High",
                "roi_score": 87,
                "why_it_helps": "Widely recognized BI credential for analyst and reporting roles.",
            },
            {
                "certificate": "Databricks Data Engineer Associate",
                "cost_usd": "$200 exam",
                "time_required": "8-12 weeks",
                "entry_salary_range": "$85k-$130k",
                "difficulty_level": "Intermediate",
                "demand_trend": "High",
                "roi_score": 80,
                "why_it_helps": "Good signal for modern data platform roles.",
            },
        ],
        "security": [
            {
                "certificate": "CompTIA Security+",
                "cost_usd": "$404 exam",
                "time_required": "8-12 weeks",
                "entry_salary_range": "$70k-$115k",
                "difficulty_level": "Intermediate",
                "demand_trend": "High",
                "roi_score": 88,
                "why_it_helps": "Frequently listed baseline credential for security analyst roles.",
            },
            {
                "certificate": "ISC2 Certified in Cybersecurity (CC)",
                "cost_usd": "Low/varies",
                "time_required": "4-8 weeks",
                "entry_salary_range": "$60k-$100k",
                "difficulty_level": "Beginner",
                "demand_trend": "High",
                "roi_score": 85,
                "why_it_helps": "Strong entry-level credential for security job pipelines.",
            },
            {
                "certificate": "SC-900 Microsoft Security Fundamentals",
                "cost_usd": "$99 exam",
                "time_required": "3-6 weeks",
                "entry_salary_range": "$65k-$105k",
                "difficulty_level": "Beginner",
                "demand_trend": "Medium-High",
                "roi_score": 81,
                "why_it_helps": "Good supporting credential for cloud identity/security basics.",
            },
        ],
        "general": [
            {
                "certificate": "Google Career Certificate (role-aligned)",
                "cost_usd": "$39-$59/month",
                "time_required": "8-16 weeks",
                "entry_salary_range": "$55k-$95k",
                "difficulty_level": "Beginner-Intermediate",
                "demand_trend": "Medium-High",
                "roi_score": 80,
                "why_it_helps": "Structured entry path while narrowing target role.",
            },
            {
                "certificate": "AWS Certified Cloud Practitioner",
                "cost_usd": "$100 exam",
                "time_required": "4-8 weeks",
                "entry_salary_range": "$65k-$100k",
                "difficulty_level": "Beginner",
                "demand_trend": "High",
                "roi_score": 78,
                "why_it_helps": "Broad baseline credential across many digital careers.",
            },
            {
                "certificate": "LinkedIn Learning + Portfolio Sprint",
                "cost_usd": "$39.99/month",
                "time_required": "4-8 weeks",
                "entry_salary_range": "$55k-$90k",
                "difficulty_level": "Beginner",
                "demand_trend": "Medium",
                "roi_score": 74,
                "why_it_helps": "Low-friction way to build evidence while defining your lane.",
            },
        ],
    }
    return options.get(track, options["general"])


def _log(db: Session, *, user_id: str, feature: str, payload: dict[str, Any], output: str, model: str) -> None:
    try:
        _log_ai_audit(
            db,
            user_id=user_id,
            feature=feature,
            prompt_input=payload,
            context_ids=None,
            model=model,
            output=output,
        )
    except Exception:
        # Audit logging must never break user-facing responses.
        try:
            db.rollback()
        except Exception:
            pass


def generate_if_i_were_you(
    db: Session,
    *,
    user_id: str,
    gpa: float | None = None,
    internship_history: str | None = None,
    industry: str | None = None,
    location: str | None = None,
) -> dict[str, Any]:
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).one_or_none()
    track = _role_track(industry, internship_history)
    market_context = _market_snapshot(db, role_hint=industry)
    payload = {
        "gpa": gpa,
        "internship_history": internship_history,
        "industry": industry,
        "location": location or (profile.state if profile else None),
        "profile": {
            "university": profile.university if profile else None,
            "semester": profile.semester if profile else None,
        },
        "market_context": market_context,
    }

    if not ai_is_configured():
        _raise_if_ai_strict(
            "AI strict mode: /user/ai/if-i-were-you requires AI provider configuration."
        )
    if ai_is_configured():
        try:
            system = (
                "You are an AI career strategist in 'If I Were You' mode. "
                "Use market_context to align recommendations with current demand trends. "
                "Use realistic steps only. Return JSON with keys: summary, fastest_path (max 4), "
                "realistic_next_moves (max 4), avoid_now (max 3), recommended_certificates (max 5), uncertainty."
            )
            parsed = _safe_json(_call_llm(system, json.dumps(payload)))
            if parsed:
                response = {
                    "summary": str(parsed.get("summary") or "Practical path generated."),
                    "fastest_path": _safe_list(parsed.get("fastest_path"), max_items=4),
                    "realistic_next_moves": _safe_list(parsed.get("realistic_next_moves"), max_items=4),
                    "avoid_now": _safe_list(parsed.get("avoid_now"), max_items=3),
                    "recommended_certificates": _unique(
                        _safe_list(parsed.get("recommended_certificates"), max_items=5)
                        + _certs_for_track(track)
                    )[:5],
                    "uncertainty": _safe_optional_text(parsed.get("uncertainty")),
                }
                _log(
                    db,
                    user_id=user_id,
                    feature="if_i_were_you",
                    payload=payload,
                    output=response["summary"],
                    model=get_active_ai_model(),
                )
                return response
        except Exception as exc:
            reason = str(exc)
            _raise_if_ai_strict(
                "AI strict mode: /user/ai/if-i-were-you generation failed. "
                f"Reason: {_truncate(reason, limit=220)}"
            )
        else:
            reason = ""
    else:
        reason = ""

    has_internship = _has_internship(internship_history)
    if has_internship:
        fastest = [
            "Convert internship work into two measurable portfolio case studies.",
            "Run a 30-day interview sprint with proof-backed answers.",
            "Apply to 25 role-matched jobs with tailored resume bullets.",
        ]
    else:
        fastest = [
            "Complete one high-ROI certificate tied to your role lane.",
            "Build two portfolio projects with live demos and impact metrics.",
            "Run a 30-day job sprint (applications + networking + interview practice).",
        ]

    response = {
        "summary": "If I were you, I would choose the shortest realistic path that compounds weekly proof and hiring signals.",
        "fastest_path": fastest,
        "realistic_next_moves": [
            "Pick one role lane and map top requirements from 20 live job posts.",
            "Ship one proof artifact weekly and publish outcomes publicly.",
            "Align resume and LinkedIn language with job-description keywords.",
            "Track response rates and iterate every week.",
        ],
        "avoid_now": [
            "Avoid collecting certificates without portfolio proof.",
            "Avoid applying blindly without role-specific tailoring.",
            "Avoid advanced topics before fundamentals are visible in your evidence.",
        ],
        "recommended_certificates": _certs_for_track(track),
        "uncertainty": f"AI unavailable; rules path used. Reason: {reason[:180]}" if reason else None,
    }
    _log(db, user_id=user_id, feature="if_i_were_you", payload=payload, output=response["summary"], model="rules-based")
    return response


def generate_certification_roi(
    db: Session,
    *,
    user_id: str,
    target_role: str | None = None,
    current_skills: str | None = None,
    location: str | None = None,
    max_budget_usd: int | None = None,
) -> dict[str, Any]:
    track = _role_track(target_role, current_skills)
    market_context = _market_snapshot(db, role_hint=target_role)
    payload = {
        "target_role": target_role,
        "current_skills": current_skills,
        "location": location,
        "max_budget_usd": max_budget_usd,
        "role_track_hint": track,
        "market_context": market_context,
    }

    fallback = _fallback_cert_roi_options(track)

    if not ai_is_configured():
        _raise_if_ai_strict(
            "AI strict mode: /user/ai/certification-roi requires AI provider configuration."
        )
    if ai_is_configured():
        try:
            system = (
                "You are an AI certification ROI calculator. "
                "Use market_context to prioritize certifications by demand trend and role relevance. "
                "Return JSON with keys: target_role, top_options (max 5), winner, recommendation, uncertainty. "
                "Each top_options row must include certificate, cost_usd, time_required, entry_salary_range, "
                "difficulty_level, demand_trend, roi_score (1-100), why_it_helps."
            )
            parsed = _safe_json(_call_llm(system, json.dumps(payload)))
            if parsed:
                rows: list[dict[str, Any]] = []
                for item in parsed.get("top_options", []) if isinstance(parsed.get("top_options"), list) else []:
                    if not isinstance(item, dict):
                        continue
                    cert = str(item.get("certificate") or "").strip()
                    if not cert:
                        continue
                    try:
                        score = int(float(item.get("roi_score") or 70))
                    except Exception:
                        score = 70
                    rows.append(
                        {
                            "certificate": cert,
                            "cost_usd": str(item.get("cost_usd") or "Unknown"),
                            "time_required": str(item.get("time_required") or "Unknown"),
                            "entry_salary_range": str(item.get("entry_salary_range") or "Unknown"),
                            "difficulty_level": str(item.get("difficulty_level") or "Unknown"),
                            "demand_trend": str(item.get("demand_trend") or "Unknown"),
                            "roi_score": max(1, min(100, score)),
                            "why_it_helps": str(item.get("why_it_helps") or "Improves role alignment."),
                        }
                    )
                if rows:
                    rows = rows[:5]
                else:
                    _raise_if_ai_strict(
                        "AI strict mode: /user/ai/certification-roi returned no usable top_options."
                    )
                    rows = fallback[:3]
                response = {
                    "target_role": str(parsed.get("target_role") or target_role or "").strip() or None,
                    "top_options": rows,
                    "winner": str(parsed.get("winner") or rows[0]["certificate"]),
                    "recommendation": str(parsed.get("recommendation") or "Start with the highest ROI certificate now."),
                    "uncertainty": _safe_optional_text(parsed.get("uncertainty")),
                }
                _log(
                    db,
                    user_id=user_id,
                    feature="certification_roi",
                    payload=payload,
                    output=response["recommendation"],
                    model=get_active_ai_model(),
                )
                return response
        except Exception as exc:
            reason = str(exc)
            _raise_if_ai_strict(
                "AI strict mode: /user/ai/certification-roi generation failed. "
                f"Reason: {_truncate(reason, limit=220)}"
            )
        else:
            reason = ""
    else:
        reason = ""

    options = fallback
    if max_budget_usd is not None:
        filtered: list[dict[str, Any]] = []
        for option in options:
            numbers = re.findall(r"\d+", str(option.get("cost_usd", "")))
            if not numbers or int(numbers[0]) <= max_budget_usd:
                filtered.append(option)
        options = filtered or options

    options = sorted(options, key=lambda row: int(row.get("roi_score", 0)), reverse=True)[:5]
    response = {
        "target_role": target_role or None,
        "top_options": options,
        "winner": options[0]["certificate"] if options else None,
        "recommendation": (
            f"Start with '{options[0]['certificate']}' and pair it with one project proof."
            if options
            else "Define target role to compute ROI."
        ),
        "uncertainty": f"AI unavailable; rules ROI used. Reason: {reason[:180]}" if reason else None,
    }
    _log(db, user_id=user_id, feature="certification_roi", payload=payload, output=response["recommendation"], model="rules-based")
    return response


def generate_emotional_reset(
    db: Session,
    *,
    user_id: str,
    story_context: str | None = None,
) -> dict[str, Any]:
    payload = {
        "story_context": story_context,
        "prompt": "Graduated But Feel Behind?",
        "market_context": _market_snapshot(db),
    }
    if not ai_is_configured():
        _raise_if_ai_strict(
            "AI strict mode: /user/ai/emotional-reset requires AI provider configuration."
        )
    if ai_is_configured():
        try:
            system = (
                "You are an empathetic career coach. "
                "Use market_context to keep reassurance practical and tied to current opportunity demand. "
                "Return JSON with keys: title, story, reframe, action_plan (max 5), uncertainty."
            )
            parsed = _safe_json(_call_llm(system, json.dumps(payload)))
            if parsed:
                response = {
                    "title": str(parsed.get("title") or "Graduated But Feel Behind?"),
                    "story": str(parsed.get("story") or ""),
                    "reframe": str(parsed.get("reframe") or ""),
                    "action_plan": _safe_list(parsed.get("action_plan"), max_items=5),
                    "uncertainty": _safe_optional_text(parsed.get("uncertainty")),
                }
                if not response["story"]:
                    response["story"] = "Feeling behind is common; a focused system can close gaps faster than panic."
                if not response["reframe"]:
                    response["reframe"] = "You are not late. You are in the strategy phase where execution matters most."
                if not response["action_plan"]:
                    response["action_plan"] = [
                        "Choose one role lane for the next 90 days.",
                        "Ship one proof-backed update every week.",
                        "Run a structured 30-day application sprint.",
                    ]
                _log(
                    db,
                    user_id=user_id,
                    feature="emotional_reset",
                    payload=payload,
                    output=response["reframe"],
                    model=get_active_ai_model(),
                )
                return response
        except Exception as exc:
            reason = str(exc)
            _raise_if_ai_strict(
                "AI strict mode: /user/ai/emotional-reset generation failed. "
                f"Reason: {_truncate(reason, limit=220)}"
            )
        else:
            reason = ""
    else:
        reason = ""

    response = {
        "title": "Graduated But Feel Behind?",
        "story": (
            "A lot of students hit this point after graduation. The market asks for proof and no one gives a clear playbook."
        ),
        "reframe": (
            "You don't need perfect timing. You need a repeatable 90-day system that produces visible outcomes."
        ),
        "action_plan": [
            "Pick one target role and one backup role.",
            "Build two portfolio projects with measurable impact.",
            "Complete one role-aligned certificate.",
            "Run a 30-day networking + application sprint.",
            "Review metrics weekly and adjust quickly.",
        ],
        "uncertainty": f"AI unavailable; rules support used. Reason: {reason[:180]}" if reason else None,
    }
    _log(db, user_id=user_id, feature="emotional_reset", payload=payload, output=response["reframe"], model="rules-based")
    return response


def generate_rebuild_90_day_plan(
    db: Session,
    *,
    user_id: str,
    current_skills: str,
    target_job: str,
    location: str | None = None,
    hours_per_week: int = 8,
) -> dict[str, Any]:
    track = _role_track(target_job, current_skills)
    market_context = _market_snapshot(db, role_hint=target_job)
    payload = {
        "current_skills": current_skills,
        "target_job": target_job,
        "location": location,
        "hours_per_week": hours_per_week,
        "track": track,
        "market_context": market_context,
    }

    if not ai_is_configured():
        _raise_if_ai_strict(
            "AI strict mode: /user/ai/rebuild-90-day requires AI provider configuration."
        )
    if ai_is_configured():
        try:
            system = (
                "You generate a structured 90-day rebuild plan for career readiness. "
                "Use market_context to prioritize high-demand skills and certificates. "
                "Return JSON with keys: summary, day_0_30 (max 6), day_31_60 (max 6), day_61_90 (max 6), "
                "weekly_targets (max 8), portfolio_targets (max 5), recommended_certificates (max 5), uncertainty."
            )
            parsed = _safe_json(_call_llm(system, json.dumps(payload)))
            if parsed:
                response = {
                    "summary": str(parsed.get("summary") or f"90-day plan targeting {target_job}."),
                    "day_0_30": _safe_list(parsed.get("day_0_30"), max_items=6),
                    "day_31_60": _safe_list(parsed.get("day_31_60"), max_items=6),
                    "day_61_90": _safe_list(parsed.get("day_61_90"), max_items=6),
                    "weekly_targets": _safe_list(parsed.get("weekly_targets"), max_items=8),
                    "portfolio_targets": _safe_list(parsed.get("portfolio_targets"), max_items=5),
                    "recommended_certificates": _unique(
                        _safe_list(parsed.get("recommended_certificates"), max_items=5)
                        + _certs_for_track(track)
                    )[:5],
                    "uncertainty": _safe_optional_text(parsed.get("uncertainty")),
                }
                _log(
                    db,
                    user_id=user_id,
                    feature="rebuild_90_day_plan",
                    payload=payload,
                    output=response["summary"],
                    model=get_active_ai_model(),
                )
                return response
        except Exception as exc:
            reason = str(exc)
            _raise_if_ai_strict(
                "AI strict mode: /user/ai/rebuild-90-day generation failed. "
                f"Reason: {_truncate(reason, limit=220)}"
            )
        else:
            reason = ""
    else:
        reason = ""

    response = {
        "summary": f"90-day rebuild plan targeting {target_job}.",
        "day_0_30": [
            "Map target job requirements from 20 real postings.",
            "Choose top 5 missing skills and schedule focused weekly sessions.",
            "Start project #1 with measurable outcome goals.",
        ],
        "day_31_60": [
            "Ship project #1 with demo, documentation, and impact metrics.",
            "Start project #2 aligned to a different high-priority requirement.",
            "Refine resume + LinkedIn with role-specific keywords.",
        ],
        "day_61_90": [
            "Ship project #2 and create concise case studies.",
            "Run mock interviews and record weak areas.",
            "Execute 30-day application + networking sprint.",
        ],
        "weekly_targets": [
            f"Commit {hours_per_week} hours per week to execution blocks.",
            "Publish one evidence-backed update each week.",
            "Track application metrics and iterate weekly.",
        ],
        "portfolio_targets": [
            "Two production-quality projects with clear outcomes.",
            "One case-study write-up per project.",
            "Public code + live demo for each project.",
        ],
        "recommended_certificates": _certs_for_track(track),
        "uncertainty": f"AI unavailable; rules plan used. Reason: {reason[:180]}" if reason else None,
    }
    _log(db, user_id=user_id, feature="rebuild_90_day_plan", payload=payload, output=response["summary"], model="rules-based")
    return response


def generate_college_gap_playbook(
    db: Session,
    *,
    user_id: str,
    target_job: str | None = None,
    current_skills: str | None = None,
) -> dict[str, Any]:
    payload = {
        "target_job": target_job,
        "current_skills": current_skills,
        "market_context": _market_snapshot(db, role_hint=target_job),
    }
    if not ai_is_configured():
        _raise_if_ai_strict(
            "AI strict mode: /user/ai/college-gap-playbook requires AI provider configuration."
        )
    if ai_is_configured():
        try:
            system = (
                "You are an AI coach creating a practical 'College Did not Teach Me This' playbook. "
                "Use market_context so advice reflects current hiring demand. "
                "Return JSON with keys: job_description_playbook (max 6), reverse_engineer_skills (max 6), "
                "project_that_recruiters_care (max 6), networking_strategy (max 6), uncertainty."
            )
            parsed = _safe_json(_call_llm(system, json.dumps(payload)))
            if parsed:
                response = {
                    "job_description_playbook": _safe_list(parsed.get("job_description_playbook"), max_items=6),
                    "reverse_engineer_skills": _safe_list(parsed.get("reverse_engineer_skills"), max_items=6),
                    "project_that_recruiters_care": _safe_list(parsed.get("project_that_recruiters_care"), max_items=6),
                    "networking_strategy": _safe_list(parsed.get("networking_strategy"), max_items=6),
                    "uncertainty": _safe_optional_text(parsed.get("uncertainty")),
                }
                _log(
                    db,
                    user_id=user_id,
                    feature="college_gap_playbook",
                    payload=payload,
                    output="Generated college-gap playbook",
                    model=get_active_ai_model(),
                )
                return response
        except Exception as exc:
            reason = str(exc)
            _raise_if_ai_strict(
                "AI strict mode: /user/ai/college-gap-playbook generation failed. "
                f"Reason: {_truncate(reason, limit=220)}"
            )
        else:
            reason = ""
    else:
        reason = ""

    response = {
        "job_description_playbook": [
            "Split each job posting into must-have vs nice-to-have skills.",
            "Track repeated requirements across 20 postings and prioritize top 5.",
            "Mirror posting keywords in your resume bullets and project summaries.",
        ],
        "reverse_engineer_skills": [
            "Convert repeated requirements into a 6-week learning map.",
            "Pair each skill with one proof artifact and one interview story.",
            "Review and update your map weekly using new posting data.",
        ],
        "project_that_recruiters_care": [
            "Build projects that solve a real pain point with measurable outcomes.",
            "Show architecture choices, tradeoffs, and final impact metrics.",
            "Ship with docs, tests, and a live demo link recruiters can verify quickly.",
        ],
        "networking_strategy": [
            "Reach out to 5 role-aligned professionals per week with a focused ask.",
            "Share weekly project updates publicly to attract recruiter attention.",
            "Follow up with a concise thank-you note and one concrete next step.",
        ],
        "uncertainty": f"AI unavailable; rules playbook used. Reason: {reason[:180]}" if reason else None,
    }
    _log(db, user_id=user_id, feature="college_gap_playbook", payload=payload, output="Generated rules college-gap playbook", model="rules-based")
    return response
