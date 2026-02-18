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
    AdminAiSummaryIn,
    AdminAiSummaryOut,
)
from app.services.ai import (
    generate_student_guidance,
    generate_admin_summary,
    log_ai_feedback,
    sync_evidence_requirement_matches,
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


@router.post("/admin/ai/summarize", response_model=AdminAiSummaryOut, dependencies=[Depends(require_admin)])
def admin_ai_summary(payload: AdminAiSummaryIn, db: Session = Depends(get_db)):
    ai_rate_limiter.check("admin")
    return generate_admin_summary(db, payload.source_text, payload.purpose)
