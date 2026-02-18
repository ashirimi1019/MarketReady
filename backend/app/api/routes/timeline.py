from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import re
from app.api.deps import get_db, get_current_user_id
from app.schemas.api import TimelineOut
from app.models.entities import UserPathway, Milestone

router = APIRouter(prefix="/user")


@router.get("/timeline", response_model=list[TimelineOut])
def timeline(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    selection = db.query(UserPathway).filter(UserPathway.user_id == user_id).one_or_none()
    if not selection:
        raise HTTPException(status_code=404, detail="No pathway selection found")

    milestones = (
        db.query(Milestone)
        .filter(Milestone.pathway_id == selection.pathway_id)
        .order_by(Milestone.semester_index.asc())
        .all()
    )

    return [
        {
            "milestone_id": m.id,
            "title": re.sub(r"(?i)\bsemester\b", "Year", m.title),
            "description": m.description,
            "semester_index": m.semester_index,
        }
        for m in milestones
    ]
