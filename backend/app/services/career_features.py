from __future__ import annotations

from datetime import datetime, timedelta
import json
import re
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import (
    AiInterviewQuestion,
    AiInterviewResponse,
    AiInterviewSession,
    AiResumeArtifact,
    ChecklistItem,
    ChecklistVersion,
    Milestone,
    Proof,
    StudentGoal,
    StudentProfile,
    UserPathway,
)
from app.services.ai import (
    _call_llm,
    _extract_resume_context,
    _log_ai_audit,
    _safe_json,
    ai_is_configured,
    ai_strict_mode_enabled,
    get_active_ai_model,
)

STREAK_REWARD_THRESHOLDS = [2, 4, 8, 12, 24]
KEYWORD_STOPWORDS = {
    "with",
    "from",
    "into",
    "that",
    "this",
    "your",
    "have",
    "has",
    "for",
    "and",
    "the",
    "a",
    "an",
    "in",
    "on",
    "to",
    "of",
    "or",
    "as",
    "is",
}


def _raise_if_ai_strict(reason: str) -> None:
    if ai_strict_mode_enabled():
        raise RuntimeError(reason)


def _start_of_week(value: datetime) -> datetime:
    monday = value.date() - timedelta(days=value.weekday())
    return datetime.combine(monday, datetime.min.time())


def _week_label(week_start: datetime) -> str:
    iso_year, iso_week, _ = week_start.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def build_weekly_streak(db: Session, user_id: str) -> dict[str, Any]:
    event_times: list[datetime] = []

    proof_rows = db.query(Proof.created_at).filter(Proof.user_id == user_id).all()
    event_times.extend([row[0] for row in proof_rows if row and row[0]])

    goals = db.query(StudentGoal).filter(StudentGoal.user_id == user_id).all()
    for goal in goals:
        if goal.updated_at:
            event_times.append(goal.updated_at)
        if goal.last_check_in_at:
            event_times.append(goal.last_check_in_at)

    active_weeks = {_start_of_week(ts) for ts in event_times}
    current_week = _start_of_week(datetime.utcnow())

    current_streak = 0
    cursor = current_week
    while cursor in active_weeks:
        current_streak += 1
        cursor -= timedelta(days=7)

    sorted_weeks = sorted(active_weeks)
    longest_streak = 0
    run = 0
    for index, week in enumerate(sorted_weeks):
        if index == 0:
            run = 1
        elif (week - sorted_weeks[index - 1]).days == 7:
            run += 1
        else:
            run = 1
        longest_streak = max(longest_streak, run)

    rewards = [
        f"{threshold}-week streak badge"
        for threshold in STREAK_REWARD_THRESHOLDS
        if current_streak >= threshold
    ]
    next_reward = next(
        (threshold for threshold in STREAK_REWARD_THRESHOLDS if threshold > current_streak),
        None,
    )

    recent_weeks = []
    for offset in range(7, -1, -1):
        week_start = current_week - timedelta(days=7 * offset)
        recent_weeks.append(
            {
                "week_start": week_start,
                "week_label": _week_label(week_start),
                "has_activity": week_start in active_weeks,
            }
        )

    return {
        "current_streak_weeks": current_streak,
        "longest_streak_weeks": longest_streak,
        "total_active_weeks": len(active_weeks),
        "active_this_week": current_week in active_weeks,
        "rewards": rewards,
        "next_reward_at_weeks": next_reward,
        "recent_weeks": recent_weeks,
    }


def _resolve_user_context(
    db: Session,
    user_id: str,
) -> tuple[list[ChecklistItem], list[Milestone], list[Proof], StudentProfile | None]:
    selection = db.query(UserPathway).filter(UserPathway.user_id == user_id).one_or_none()
    version: ChecklistVersion | None = None
    items: list[ChecklistItem] = []
    milestones: list[Milestone] = []
    if selection:
        if selection.checklist_version_id:
            version = db.query(ChecklistVersion).get(selection.checklist_version_id)
        if not version:
            version = (
                db.query(ChecklistVersion)
                .filter(ChecklistVersion.pathway_id == selection.pathway_id)
                .filter(ChecklistVersion.status == "published")
                .order_by(ChecklistVersion.version_number.desc())
                .first()
            )

        if version:
            items = db.query(ChecklistItem).filter(ChecklistItem.version_id == version.id).all()

        milestones = (
            db.query(Milestone)
            .filter(Milestone.pathway_id == selection.pathway_id)
            .order_by(Milestone.semester_index.asc())
            .all()
        )
    proofs = (
        db.query(Proof)
        .filter(Proof.user_id == user_id)
        .order_by(Proof.created_at.desc())
        .all()
    )
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).one_or_none()
    return items, milestones, proofs, profile


def _serialize_response(response: AiInterviewResponse) -> dict[str, Any]:
    return {
        "id": response.id,
        "session_id": response.session_id,
        "question_id": response.question_id,
        "answer_text": response.answer_text,
        "video_url": response.video_url,
        "ai_feedback": response.ai_feedback,
        "ai_score": response.ai_score,
        "confidence": response.confidence,
        "submitted_at": response.submitted_at,
    }


def _serialize_session(
    session: AiInterviewSession,
    questions: list[AiInterviewQuestion],
    responses: list[AiInterviewResponse],
    item_map: dict[str, ChecklistItem],
    milestone_map: dict[str, Milestone],
) -> dict[str, Any]:
    return {
        "id": session.id,
        "target_role": session.target_role,
        "job_description": session.job_description,
        "question_count": session.question_count,
        "status": session.status,
        "summary": session.summary,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "questions": [
            {
                "id": row.id,
                "order_index": row.order_index,
                "prompt": row.prompt,
                "focus_item_id": row.focus_item_id,
                "focus_title": (
                    item_map[str(row.focus_item_id)].title
                    if row.focus_item_id and str(row.focus_item_id) in item_map
                    else None
                ),
                "focus_milestone_id": row.focus_milestone_id,
                "focus_milestone_title": (
                    milestone_map[str(row.focus_milestone_id)].title
                    if row.focus_milestone_id and str(row.focus_milestone_id) in milestone_map
                    else None
                ),
                "source_proof_id": row.source_proof_id,
                "difficulty": row.difficulty,
            }
            for row in sorted(questions, key=lambda x: x.order_index)
        ],
        "responses": [_serialize_response(row) for row in responses],
    }


def _fallback_questions(count: int, items: list[ChecklistItem], milestones: list[Milestone]) -> tuple[list[dict[str, Any]], str]:
    rows: list[dict[str, Any]] = []
    for item in items:
        rows.append(
            {
                "prompt": f"Tell me how you delivered '{item.title}' and how you validated production readiness.",
                "focus_item_id": item.id,
                "focus_milestone_id": None,
                "source_proof_id": None,
                "difficulty": "intermediate",
            }
        )
        if len(rows) >= count:
            break
    if len(rows) < count:
        for milestone in milestones:
            rows.append(
                {
                    "prompt": f"Milestone check ({milestone.title}): what outcome would you deliver this year and how would you prove it?",
                    "focus_item_id": None,
                    "focus_milestone_id": milestone.id,
                    "source_proof_id": None,
                    "difficulty": "foundational",
                }
            )
            if len(rows) >= count:
                break
    while len(rows) < count:
        rows.append(
            {
                "prompt": "Describe a project where you handled ambiguity, constraints, and measurable outcomes.",
                "focus_item_id": None,
                "focus_milestone_id": None,
                "source_proof_id": None,
                "difficulty": "foundational",
            }
        )
    return rows[:count], "Practice interview generated from your checklist and milestone context."


def _ai_questions(
    count: int,
    target_role: str | None,
    job_description: str | None,
    items: list[ChecklistItem],
    milestones: list[Milestone],
    proofs: list[Proof],
) -> tuple[list[dict[str, Any]], str | None]:
    system = (
        "Generate mock interview questions for a student using proof-backed milestones. "
        "Return strict JSON: {questions:[{prompt,focus_item_id,focus_milestone_id,source_proof_id,difficulty}],summary}. "
        f"Return exactly {count} questions."
    )
    payload = {
        "target_role": target_role,
        "job_description": job_description,
        "items": [{"id": str(i.id), "title": i.title, "tier": i.tier} for i in items],
        "milestones": [{"id": str(m.id), "title": m.title} for m in milestones],
        "proofs": [
            {
                "id": str(p.id),
                "checklist_item_id": str(p.checklist_item_id),
                "proof_type": p.proof_type,
                "status": p.status,
            }
            for p in proofs[:20]
        ],
    }
    parsed = _safe_json(_call_llm(system, json.dumps(payload)))
    if not parsed:
        return [], None
    item_ids = {str(i.id) for i in items}
    milestone_ids = {str(m.id) for m in milestones}
    proof_ids = {str(p.id) for p in proofs}
    rows: list[dict[str, Any]] = []
    for row in parsed.get("questions", []):
        prompt = str(row.get("prompt") or "").strip()
        if not prompt:
            continue
        focus_item_id = str(row.get("focus_item_id")) if row.get("focus_item_id") else None
        focus_milestone_id = str(row.get("focus_milestone_id")) if row.get("focus_milestone_id") else None
        source_proof_id = str(row.get("source_proof_id")) if row.get("source_proof_id") else None
        rows.append(
            {
                "prompt": prompt,
                "focus_item_id": focus_item_id if focus_item_id in item_ids else None,
                "focus_milestone_id": (
                    focus_milestone_id if focus_milestone_id in milestone_ids else None
                ),
                "source_proof_id": source_proof_id if source_proof_id in proof_ids else None,
                "difficulty": str(row.get("difficulty") or "intermediate"),
            }
        )
        if len(rows) >= count:
            break
    return rows, str(parsed.get("summary") or "").strip() or None


def create_interview_session(
    db: Session,
    user_id: str,
    *,
    target_role: str | None,
    job_description: str | None,
    question_count: int,
) -> dict[str, Any]:
    count = max(3, min(int(question_count), 10))
    items, milestones, proofs, _ = _resolve_user_context(db, user_id)

    questions_data: list[dict[str, Any]] = []
    summary: str | None = None
    ai_failure_reason: str | None = None
    if not ai_is_configured():
        ai_failure_reason = "AI provider is not configured."
    if ai_is_configured():
        try:
            questions_data, summary = _ai_questions(
                count, target_role, job_description, items, milestones, proofs
            )
        except Exception as exc:
            ai_failure_reason = str(exc)
            questions_data = []
    if not questions_data:
        _raise_if_ai_strict(
            "AI strict mode: interview session generation failed. "
            f"Reason: {(ai_failure_reason or 'No questions returned by model.')[:220]}"
        )
        questions_data, fallback_summary = _fallback_questions(count, items, milestones)
        summary = summary or fallback_summary

    now = datetime.utcnow()
    session = AiInterviewSession(
        user_id=user_id,
        target_role=target_role,
        job_description=job_description,
        question_count=count,
        status="active",
        summary=summary,
        created_at=now,
        updated_at=now,
    )
    db.add(session)
    db.flush()

    created_questions: list[AiInterviewQuestion] = []
    for index, row in enumerate(questions_data, start=1):
        question = AiInterviewQuestion(
            session_id=session.id,
            order_index=index,
            prompt=row["prompt"],
            focus_item_id=row.get("focus_item_id"),
            focus_milestone_id=row.get("focus_milestone_id"),
            source_proof_id=row.get("source_proof_id"),
            difficulty=row.get("difficulty"),
            created_at=now,
        )
        db.add(question)
        created_questions.append(question)

    db.commit()
    db.refresh(session)
    for question in created_questions:
        db.refresh(question)

    _log_ai_audit(
        db,
        user_id=user_id,
        feature="interview_session_generate",
        prompt_input={"target_role": target_role, "question_count": count},
        context_ids=[str(q.id) for q in created_questions],
        model=get_active_ai_model() if ai_is_configured() else "n/a",
        output=session.summary,
    )
    item_map = {str(item.id): item for item in items}
    milestone_map = {str(milestone.id): milestone for milestone in milestones}
    return _serialize_session(session, created_questions, [], item_map, milestone_map)


def list_interview_sessions(db: Session, user_id: str, limit: int = 10) -> list[dict[str, Any]]:
    sessions = (
        db.query(AiInterviewSession)
        .filter(AiInterviewSession.user_id == user_id)
        .order_by(AiInterviewSession.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": s.id,
            "target_role": s.target_role,
            "job_description": s.job_description,
            "question_count": s.question_count,
            "status": s.status,
            "summary": s.summary,
            "created_at": s.created_at,
            "updated_at": s.updated_at,
            "questions": [],
            "responses": [],
        }
        for s in sessions
    ]


def get_interview_session(db: Session, user_id: str, session_id: str) -> dict[str, Any]:
    session = db.query(AiInterviewSession).get(session_id)
    if not session or session.user_id != user_id:
        raise ValueError("Interview session not found")
    questions = (
        db.query(AiInterviewQuestion)
        .filter(AiInterviewQuestion.session_id == session.id)
        .order_by(AiInterviewQuestion.order_index.asc())
        .all()
    )
    responses = (
        db.query(AiInterviewResponse)
        .filter(AiInterviewResponse.session_id == session.id)
        .order_by(AiInterviewResponse.submitted_at.asc())
        .all()
    )
    item_ids = [q.focus_item_id for q in questions if q.focus_item_id]
    milestone_ids = [q.focus_milestone_id for q in questions if q.focus_milestone_id]
    items = db.query(ChecklistItem).filter(ChecklistItem.id.in_(item_ids)).all() if item_ids else []
    milestones = (
        db.query(Milestone).filter(Milestone.id.in_(milestone_ids)).all()
        if milestone_ids
        else []
    )
    item_map = {str(item.id): item for item in items}
    milestone_map = {str(m.id): m for m in milestones}
    return _serialize_session(session, questions, responses, item_map, milestone_map)


def _fallback_feedback(prompt: str, answer_text: str, has_video: bool) -> tuple[float, float, str]:
    length_score = min(len(answer_text) / 700, 1.0)
    metric_bonus = 0.08 if re.search(r"\b\d+[%xkmb]?\b", answer_text.lower()) else 0.0
    detail_bonus = 0.08 if "trade" in answer_text.lower() or "impact" in answer_text.lower() else 0.0
    video_bonus = 0.04 if has_video else 0.0
    score = max(35.0, min((0.45 + 0.35 * length_score + metric_bonus + detail_bonus + video_bonus) * 100, 96.0))
    feedback = (
        f"Score {score:.1f}/100. Improve by using STAR format and quantified outcomes. "
        f"Question: {prompt}"
    )
    return round(score, 1), 0.55, feedback


def submit_interview_response(
    db: Session,
    user_id: str,
    *,
    session_id: str,
    question_id: str,
    answer_text: str | None,
    video_url: str | None,
) -> dict[str, Any]:
    session = db.query(AiInterviewSession).get(session_id)
    if not session or session.user_id != user_id:
        raise ValueError("Interview session not found")
    question = db.query(AiInterviewQuestion).get(question_id)
    if not question or question.session_id != session.id:
        raise ValueError("Interview question not found")

    answer = (answer_text or "").strip()
    video = (video_url or "").strip() or None
    if not answer and not video:
        raise ValueError("Provide an answer text or a video URL")

    score: float
    confidence: float
    feedback: str
    if video and not answer:
        _raise_if_ai_strict(
            "AI strict mode: provide answer_text (transcript) so interview scoring can run through AI."
        )
        score, confidence, feedback = (
            45.0,
            0.4,
            "Video received. Add a short transcript for a full AI quality score.",
        )
    elif ai_is_configured():
        try:
            parsed = _safe_json(
                _call_llm(
                    "Evaluate a student interview answer. Return JSON: {score,confidence,feedback}.",
                    json.dumps(
                        {
                            "question": question.prompt,
                            "answer_text": answer,
                            "video_url": video,
                            "target_role": session.target_role,
                        }
                    ),
                )
            )
            if not parsed:
                raise ValueError("unparsed")
            score = float(parsed.get("score", 0.0))
            confidence = float(parsed.get("confidence", 0.0))
            feedback = str(parsed.get("feedback") or "").strip() or "Feedback unavailable."
        except Exception as exc:
            _raise_if_ai_strict(
                "AI strict mode: interview response scoring failed. "
                f"Reason: {str(exc)[:220]}"
            )
            score, confidence, feedback = _fallback_feedback(question.prompt, answer, bool(video))
    else:
        _raise_if_ai_strict(
            "AI strict mode: interview response scoring requires AI provider configuration."
        )
        score, confidence, feedback = _fallback_feedback(question.prompt, answer, bool(video))

    now = datetime.utcnow()
    response = (
        db.query(AiInterviewResponse)
        .filter(AiInterviewResponse.question_id == question.id)
        .one_or_none()
    )
    if response:
        response.answer_text = answer or None
        response.video_url = video
        response.ai_feedback = feedback
        response.ai_score = score
        response.confidence = confidence
        response.submitted_at = now
    else:
        response = AiInterviewResponse(
            session_id=session.id,
            question_id=question.id,
            answer_text=answer or None,
            video_url=video,
            ai_feedback=feedback,
            ai_score=score,
            confidence=confidence,
            submitted_at=now,
        )
        db.add(response)

    all_scores = (
        db.query(AiInterviewResponse.ai_score)
        .filter(AiInterviewResponse.session_id == session.id)
        .all()
    )
    numeric_scores = [float(row[0]) for row in all_scores if row and row[0] is not None]
    question_count = (
        db.query(AiInterviewQuestion)
        .filter(AiInterviewQuestion.session_id == session.id)
        .count()
    )
    answered = (
        db.query(AiInterviewResponse)
        .filter(AiInterviewResponse.session_id == session.id)
        .count()
    )
    avg_score = (sum(numeric_scores) / len(numeric_scores)) if numeric_scores else 0.0
    session.status = "completed" if answered >= question_count and question_count > 0 else "active"
    session.summary = (
        f"Progress {answered}/{question_count}. Average score {avg_score:.1f}/100."
        if session.status == "active"
        else f"Interview complete. Average score {avg_score:.1f}/100."
    )
    session.updated_at = now
    db.commit()
    db.refresh(response)

    _log_ai_audit(
        db,
        user_id=user_id,
        feature="interview_response_feedback",
        prompt_input={"session_id": str(session.id), "question_id": str(question.id)},
        context_ids=[str(question.id)],
        model=get_active_ai_model() if ai_is_configured() else "n/a",
        output=feedback,
    )
    return _serialize_response(response)


def _extract_keywords(text: str | None, limit: int = 15) -> list[str]:
    if not text:
        return []
    keywords: list[str] = []
    for token in re.findall(r"[a-zA-Z0-9+#.-]+", text.lower()):
        if len(token) < 3 or token in KEYWORD_STOPWORDS:
            continue
        if token in keywords:
            continue
        keywords.append(token)
        if len(keywords) >= limit:
            break
    return keywords


def _serialize_resume_artifact(artifact: AiResumeArtifact) -> dict[str, Any]:
    return {
        "id": artifact.id,
        "target_role": artifact.target_role,
        "job_description": artifact.job_description,
        "ats_keywords": artifact.ats_keywords if isinstance(artifact.ats_keywords, list) else [],
        "markdown_content": artifact.markdown_content,
        "structured": artifact.structured_json if isinstance(artifact.structured_json, dict) else None,
        "created_at": artifact.created_at,
    }


def generate_resume_artifact(
    db: Session,
    user_id: str,
    *,
    target_role: str | None,
    job_description: str | None,
) -> dict[str, Any]:
    items, _, proofs, profile = _resolve_user_context(db, user_id)
    resume_context = _extract_resume_context(profile)
    keywords = _extract_keywords(job_description, limit=20)
    markdown = ""
    structured: dict[str, Any] | None = None
    model_used = "n/a"
    ai_failure_reason: str | None = None

    if not ai_is_configured():
        ai_failure_reason = "AI provider is not configured."

    if ai_is_configured():
        try:
            parsed = _safe_json(
                _call_llm(
                    "Build ATS resume markdown from student proof data. Return JSON: {markdown_content,ats_keywords,structured}.",
                    json.dumps(
                        {
                            "user_id": user_id,
                            "target_role": target_role,
                            "job_description": job_description,
                            "profile": {
                                "semester": profile.semester if profile else None,
                                "state": profile.state if profile else None,
                                "university": profile.university if profile else None,
                            },
                            "resume_context": resume_context,
                            "proofs": [
                                {
                                    "id": str(proof.id),
                                    "proof_type": proof.proof_type,
                                    "status": proof.status,
                                    "url": proof.url,
                                }
                                for proof in proofs[:20]
                            ],
                            "checklist_items": [
                                {"title": item.title, "tier": item.tier}
                                for item in items[:20]
                            ],
                        }
                    ),
                )
            )
            if parsed and parsed.get("markdown_content"):
                markdown = str(parsed.get("markdown_content"))
                if isinstance(parsed.get("ats_keywords"), list):
                    keywords = [str(k) for k in parsed["ats_keywords"]][:20]
                if isinstance(parsed.get("structured"), dict):
                    structured = parsed["structured"]
                model_used = get_active_ai_model()
        except Exception as exc:
            ai_failure_reason = str(exc)
            markdown = ""

    if not markdown:
        _raise_if_ai_strict(
            "AI strict mode: resume architect generation failed. "
            f"Reason: {(ai_failure_reason or 'No markdown content returned by model.')[:220]}"
        )
        skill_titles = [item.title for item in items[:8]]
        proof_lines = [
            f"- {proof.proof_type.replace('_', ' ').title()}: {proof.url}"
            for proof in proofs[:6]
        ]
        markdown = "\n".join(
            [
                f"# {user_id}",
                "",
                "## Target Role",
                target_role or "Not specified",
                "",
                "## Summary",
                "Proof-backed candidate focused on measurable outcomes and production-quality delivery.",
                "",
                "## Core Skills",
                ", ".join(skill_titles) if skill_titles else "Populate after checklist progress.",
                "",
                "## Proof-Backed Experience",
                "\n".join(proof_lines) if proof_lines else "- Add submitted proofs to populate this section.",
                "",
                "## Education",
                f"- University: {profile.university if profile and profile.university else 'Not provided'}",
                f"- Academic Stage: {profile.semester if profile and profile.semester else 'Not provided'}",
                "",
                "## ATS Keywords",
                ", ".join(keywords) if keywords else "No keywords extracted",
            ]
        )
        structured = {
            "core_skills": skill_titles,
            "proof_count": len(proofs),
        }

    artifact = AiResumeArtifact(
        user_id=user_id,
        target_role=target_role,
        job_description=job_description,
        ats_keywords=keywords,
        markdown_content=markdown,
        structured_json=structured,
        created_at=datetime.utcnow(),
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)

    _log_ai_audit(
        db,
        user_id=user_id,
        feature="resume_architect_generate",
        prompt_input={"target_role": target_role},
        context_ids=[str(artifact.id)],
        model=model_used,
        output=markdown[:1000],
    )
    return _serialize_resume_artifact(artifact)


def list_resume_artifacts(db: Session, user_id: str, limit: int = 10) -> list[dict[str, Any]]:
    rows = (
        db.query(AiResumeArtifact)
        .filter(AiResumeArtifact.user_id == user_id)
        .order_by(AiResumeArtifact.created_at.desc())
        .limit(limit)
        .all()
    )
    return [_serialize_resume_artifact(row) for row in rows]
