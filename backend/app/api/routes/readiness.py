from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import re
from urllib.parse import quote
from collections import defaultdict
from app.api.deps import get_db, get_current_user_id
from app.schemas.api import ReadinessOut, ReadinessRankOut, WeeklyMilestoneStreakOut
from app.models.entities import ChecklistItem, Proof, UserPathway, ChecklistVersion, Milestone, StudentProfile
from app.core.config import settings
from app.services.readiness import calculate_unified_readiness
from app.services.career_features import build_weekly_streak

router = APIRouter(prefix="/user")


def _resolve_version_id(selection: UserPathway, db: Session):
    version_id = selection.checklist_version_id
    if version_id:
        return version_id
    version = (
        db.query(ChecklistVersion)
        .filter(ChecklistVersion.pathway_id == selection.pathway_id)
        .filter(ChecklistVersion.status == "published")
        .order_by(ChecklistVersion.version_number.desc())
        .first()
    )
    if not version:
        return None
    return version.id


def _load_readiness(
    selection: UserPathway,
    db: Session,
    *,
    profile: StudentProfile | None = None,
    engineering_cache: dict[str, dict] | None = None,
    market_alignment_cache: dict[str, dict] | None = None,
) -> dict:
    version_id = _resolve_version_id(selection, db)
    if not version_id:
        raise HTTPException(status_code=404, detail="No published checklist version")

    items = db.query(ChecklistItem).filter(ChecklistItem.version_id == version_id).all()
    proofs = db.query(Proof).filter(Proof.user_id == selection.user_id).all()
    score = calculate_unified_readiness(
        db,
        selection,
        items,
        proofs,
        profile=profile,
        engineering_cache=engineering_cache,
        market_alignment_cache=market_alignment_cache,
    )

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


@router.get("/readiness", response_model=ReadinessOut)
def readiness(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    selection = db.query(UserPathway).filter(UserPathway.user_id == user_id).one_or_none()
    if not selection:
        raise HTTPException(status_code=404, detail="No pathway selection found")
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).one_or_none()
    return _load_readiness(selection, db, profile=profile)


@router.get("/readiness/rank", response_model=ReadinessRankOut)
def readiness_rank(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    selection = db.query(UserPathway).filter(UserPathway.user_id == user_id).one_or_none()
    if not selection:
        raise HTTPException(status_code=404, detail="No pathway selection found")

    selections = db.query(UserPathway).all()
    user_ids = [row.user_id for row in selections]
    profiles_by_user = {
        row.user_id: row
        for row in db.query(StudentProfile)
        .filter(StudentProfile.user_id.in_(user_ids))
        .all()
    } if user_ids else {}
    engineering_cache: dict[str, dict] = {}
    market_alignment_cache: dict[str, dict] = {}

    current_score = _load_readiness(
        selection,
        db,
        profile=profiles_by_user.get(user_id),
        engineering_cache=engineering_cache,
        market_alignment_cache=market_alignment_cache,
    )
    proofs_by_user: dict[str, list[Proof]] = defaultdict(list)
    all_proofs = db.query(Proof).all()
    for proof in all_proofs:
        proofs_by_user[proof.user_id].append(proof)

    version_items_cache: dict[str, list[ChecklistItem]] = {}
    pathway_version_cache: dict[str, ChecklistVersion | None] = {}
    scores: list[tuple[str, float]] = []

    for row in selections:
        version_id = row.checklist_version_id
        if not version_id:
            pathway_key = str(row.pathway_id)
            if pathway_key not in pathway_version_cache:
                pathway_version_cache[pathway_key] = (
                    db.query(ChecklistVersion)
                    .filter(ChecklistVersion.pathway_id == row.pathway_id)
                    .filter(ChecklistVersion.status == "published")
                    .order_by(ChecklistVersion.version_number.desc())
                    .first()
                )
            latest_version = pathway_version_cache[pathway_key]
            if not latest_version:
                continue
            version_id = latest_version.id

        version_key = str(version_id)
        if version_key not in version_items_cache:
            version_items_cache[version_key] = (
                db.query(ChecklistItem)
                .filter(ChecklistItem.version_id == version_id)
                .all()
            )
        score_row = calculate_unified_readiness(
            db,
            row,
            version_items_cache[version_key],
            proofs_by_user.get(row.user_id, []),
            profile=profiles_by_user.get(row.user_id),
            engineering_cache=engineering_cache,
            market_alignment_cache=market_alignment_cache,
        )
        scores.append((row.user_id, float(score_row["score"])))

    if not scores:
        raise HTTPException(status_code=404, detail="No students available for ranking")

    total_students = len(scores)
    current_user_score = float(current_score["score"])
    greater_count = sum(1 for _, score in scores if score > current_user_score)
    lower_count = sum(1 for _, score in scores if score < current_user_score)
    equal_count = total_students - greater_count - lower_count

    rank = greater_count + 1
    percentile = round(((lower_count + 0.5 * equal_count) / total_students) * 100, 1)
    top_percent = max(1, int(round(100 - percentile + 1)))

    share_text = (
        f"I scored {current_user_score:.0f}/100 on Market Ready "
        f"({current_score['band']}) and currently rank Top {top_percent}% "
        "based on proof-backed readiness metrics."
    )
    share_url = (
        "https://www.linkedin.com/sharing/share-offsite/?url="
        + quote(settings.public_app_base_url, safe="")
    )

    return {
        "score": current_user_score,
        "band": current_score["band"],
        "percentile": percentile,
        "rank": rank,
        "total_students": total_students,
        "linkedin_share_text": share_text,
        "linkedin_share_url": share_url,
    }


@router.get("/streak", response_model=WeeklyMilestoneStreakOut)
def weekly_milestone_streak(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return build_weekly_streak(db, user_id)
