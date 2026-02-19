from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user_id, require_admin
from app.core.ratelimit import ai_rate_limiter
from app.schemas.api import (
    AiGuideIn,
    AiGuideOut,
    AiEvidenceMapOut,
    AiGuideFeedbackIn,
    AiGuideFeedbackOut,
    AiInterviewSessionIn,
    AiInterviewSessionOut,
    AiInterviewResponseIn,
    AiInterviewResponseOut,
    AiResumeArchitectIn,
    AiResumeArtifactOut,
    AdminAiSummaryIn,
    AdminAiSummaryOut,
)
from app.services.ai import (
    generate_student_guidance,
    generate_admin_summary,
    log_ai_feedback,
    sync_evidence_requirement_matches,
)
from app.services.career_features import (
    create_interview_session,
    get_interview_session,
    list_interview_sessions,
    submit_interview_response,
    generate_resume_artifact,
    list_resume_artifacts,
)

router = APIRouter()


@router.post("/user/ai/guide", response_model=AiGuideOut)
def student_ai_guide(
    payload: AiGuideIn,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ai_rate_limiter.check(f"user:{user_id}")
    try:
        return generate_student_guidance(db, user_id, payload.question)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/user/ai/evidence-map", response_model=AiEvidenceMapOut)
def student_ai_evidence_mapper(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ai_rate_limiter.check(f"user:{user_id}:evidence-map")
    return sync_evidence_requirement_matches(db, user_id)


@router.post("/user/ai/guide/feedback", response_model=AiGuideFeedbackOut)
def student_ai_guide_feedback(
    payload: AiGuideFeedbackIn,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ai_rate_limiter.check(f"user:{user_id}:guide-feedback")
    log_ai_feedback(
        db,
        user_id=user_id,
        helpful=payload.helpful,
        comment=payload.comment,
        context_ids=[str(value) for value in payload.context_item_ids],
    )
    return {"ok": True, "message": "Thanks. Feedback saved."}


@router.post("/user/ai/interview/sessions", response_model=AiInterviewSessionOut)
def student_ai_interview_create_session(
    payload: AiInterviewSessionIn,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ai_rate_limiter.check(f"user:{user_id}:interview-create")
    try:
        return create_interview_session(
            db,
            user_id,
            target_role=payload.target_role,
            job_description=payload.job_description,
            question_count=payload.question_count,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/user/ai/interview/sessions", response_model=list[AiInterviewSessionOut])
def student_ai_interview_list_sessions(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ai_rate_limiter.check(f"user:{user_id}:interview-list")
    return list_interview_sessions(db, user_id)


@router.get("/user/ai/interview/sessions/{session_id}", response_model=AiInterviewSessionOut)
def student_ai_interview_get_session(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ai_rate_limiter.check(f"user:{user_id}:interview-get")
    try:
        return get_interview_session(db, user_id, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/user/ai/interview/sessions/{session_id}/responses",
    response_model=AiInterviewResponseOut,
)
def student_ai_interview_submit_response(
    session_id: str,
    payload: AiInterviewResponseIn,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ai_rate_limiter.check(f"user:{user_id}:interview-response")
    try:
        return submit_interview_response(
            db,
            user_id,
            session_id=session_id,
            question_id=str(payload.question_id),
            answer_text=payload.answer_text,
            video_url=payload.video_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/user/ai/resume-architect", response_model=AiResumeArtifactOut)
def student_ai_resume_architect_generate(
    payload: AiResumeArchitectIn,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ai_rate_limiter.check(f"user:{user_id}:resume-architect-generate")
    try:
        return generate_resume_artifact(
            db,
            user_id,
            target_role=payload.target_role,
            job_description=payload.job_description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/user/ai/resume-architect", response_model=list[AiResumeArtifactOut])
def student_ai_resume_architect_list(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ai_rate_limiter.check(f"user:{user_id}:resume-architect-list")
    return list_resume_artifacts(db, user_id)


@router.post("/admin/ai/summarize", response_model=AdminAiSummaryOut, dependencies=[Depends(require_admin)])
def admin_ai_summary(payload: AdminAiSummaryIn, db: Session = Depends(get_db)):
    ai_rate_limiter.check("admin")
    return generate_admin_summary(db, payload.source_text, payload.purpose)
