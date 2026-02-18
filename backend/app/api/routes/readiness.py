from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import re
from app.api.deps import get_db, get_current_user_id
from app.schemas.api import ReadinessOut
from app.models.entities import ChecklistItem, Proof, UserPathway, ChecklistVersion, Milestone
from app.services.readiness import calculate_readiness

router = APIRouter(prefix="/user")


@router.get("/readiness", response_model=ReadinessOut)
def readiness(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    selection = db.query(UserPathway).filter(UserPathway.user_id == user_id).one_or_none()
    if not selection:
        raise HTTPException(status_code=404, detail="No pathway selection found")

    version_id = selection.checklist_version_id
    if not version_id:
        version = (
            db.query(ChecklistVersion)
            .filter(ChecklistVersion.pathway_id == selection.pathway_id)
            .filter(ChecklistVersion.status == "published")
            .order_by(ChecklistVersion.version_number.desc())
            .first()
        )
        if not version:
            raise HTTPException(status_code=404, detail="No published checklist version")
        version_id = version.id

    items = db.query(ChecklistItem).filter(ChecklistItem.version_id == version_id).all()
    proofs = db.query(Proof).filter(Proof.user_id == user_id).all()

    score = calculate_readiness(items, proofs)

    milestone = (
        db.query(Milestone)
        .filter(Milestone.pathway_id == selection.pathway_id)
        .order_by(Milestone.semester_index.asc())
        .first()
    )
    if milestone and milestone.title not in score.get("next_actions", []):
        score["next_actions"] = score.get("next_actions", []) + [
            f"Review milestone: {re.sub(r'(?i)\\bsemester\\b', 'Year', milestone.title)}"
        ]
    return score
