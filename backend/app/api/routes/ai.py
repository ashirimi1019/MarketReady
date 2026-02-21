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
    AiIfIWereYouIn,
    AiIfIWereYouOut,
    AiCertRoiIn,
    AiCertRoiOut,
    AiEmotionalResetIn,
    AiEmotionalResetOut,
    AiRebuildPlanIn,
    AiRebuildPlanOut,
    AiCollegeGapIn,
    AiCollegeGapOut,
    MarketStressTestIn,
    MarketStressTestOut,
    RepoProofCheckerIn,
    RepoProofCheckerOut,
    AICareerOrchestratorIn,
    AICareerOrchestratorOut,
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
from app.services.ai_suite import (
    generate_if_i_were_you,
    generate_certification_roi,
    generate_emotional_reset,
    generate_rebuild_90_day_plan,
    generate_college_gap_playbook,
)
from app.services.career_features import (
    create_interview_session,
    get_interview_session,
    list_interview_sessions,
    submit_interview_response,
    generate_resume_artifact,
    list_resume_artifacts,
)
from app.services.market_stress import compute_market_stress_test, repo_proof_checker
from app.services.ai_orchestrator import run_ai_career_orchestrator

router = APIRouter()


@router.post("/user/ai/guide", response_model=AiGuideOut)
def student_ai_guide(
    payload: AiGuideIn,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ai_rate_limiter.check(f"user:{user_id}")
    try:
        return generate_student_guidance(
            db,
            user_id,
            question=payload.question,
            context_text=payload.context_text,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/user/ai/if-i-were-you", response_model=AiIfIWereYouOut)
def student_ai_if_i_were_you(
    payload: AiIfIWereYouIn,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ai_rate_limiter.check(f"user:{user_id}:if-i-were-you")
    try:
        return generate_if_i_were_you(
            db,
            user_id=user_id,
            gpa=payload.gpa,
            internship_history=payload.internship_history,
            industry=payload.industry,
            location=payload.location,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/user/ai/certification-roi", response_model=AiCertRoiOut)
def student_ai_certification_roi(
    payload: AiCertRoiIn,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ai_rate_limiter.check(f"user:{user_id}:certification-roi")
    try:
        return generate_certification_roi(
            db,
            user_id=user_id,
            target_role=payload.target_role,
            current_skills=payload.current_skills,
            location=payload.location,
            max_budget_usd=payload.max_budget_usd,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/user/ai/emotional-reset", response_model=AiEmotionalResetOut)
def student_ai_emotional_reset(
    payload: AiEmotionalResetIn,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ai_rate_limiter.check(f"user:{user_id}:emotional-reset")
    try:
        return generate_emotional_reset(
            db,
            user_id=user_id,
            story_context=payload.story_context,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/user/ai/rebuild-90-day", response_model=AiRebuildPlanOut)
def student_ai_rebuild_90_day(
    payload: AiRebuildPlanIn,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ai_rate_limiter.check(f"user:{user_id}:rebuild-90-day")
    try:
        return generate_rebuild_90_day_plan(
            db,
            user_id=user_id,
            current_skills=payload.current_skills,
            target_job=payload.target_job,
            location=payload.location,
            hours_per_week=payload.hours_per_week or 8,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/user/ai/college-gap-playbook", response_model=AiCollegeGapOut)
def student_ai_college_gap_playbook(
    payload: AiCollegeGapIn,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ai_rate_limiter.check(f"user:{user_id}:college-gap-playbook")
    try:
        return generate_college_gap_playbook(
            db,
            user_id=user_id,
            target_job=payload.target_job,
            current_skills=payload.current_skills,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/user/ai/market-stress-test", response_model=MarketStressTestOut)
def student_market_stress_test(
    payload: MarketStressTestIn,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ai_rate_limiter.check(f"user:{user_id}:market-stress-test")
    try:
        return compute_market_stress_test(
            db,
            user_id=user_id,
            target_job=payload.target_job,
            location=payload.location,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/user/ai/proof-checker", response_model=RepoProofCheckerOut)
def student_repo_proof_checker(
    payload: RepoProofCheckerIn,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ai_rate_limiter.check(f"user:{user_id}:proof-checker")
    try:
        return repo_proof_checker(
            db,
            user_id=user_id,
            target_job=payload.target_job,
            location=payload.location,
            repo_url=payload.repo_url,
            proof_id=str(payload.proof_id) if payload.proof_id else None,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/user/ai/orchestrator", response_model=AICareerOrchestratorOut)
def student_ai_orchestrator(
    payload: AICareerOrchestratorIn,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ai_rate_limiter.check(f"user:{user_id}:ai-orchestrator")
    try:
        return run_ai_career_orchestrator(
            db,
            user_id=user_id,
            target_job=payload.target_job,
            location=payload.location,
            availability_hours_per_week=payload.availability_hours_per_week,
            pivot_requested=payload.pivot_requested,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/user/ai/evidence-map", response_model=AiEvidenceMapOut)
def student_ai_evidence_mapper(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ai_rate_limiter.check(f"user:{user_id}:evidence-map")
    try:
        return sync_evidence_requirement_matches(db, user_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


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
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
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
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
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
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
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
    try:
        return generate_admin_summary(db, payload.source_text, payload.purpose)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
