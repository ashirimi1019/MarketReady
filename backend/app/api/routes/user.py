from datetime import datetime
import logging
import os
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.api.deps import get_db, get_current_user_id
from app.core.config import settings
from app.models.entities import (
    ChecklistItem,
    ChecklistVersion,
    Cohort,
    Proof,
    StudentGoal,
    StudentNotification,
    StudentProfile,
    UserPathway,
)
from app.services.ai import RESUME_MATCH_PROOF_TYPE, sync_resume_requirement_matches
from app.services.storage import resolve_file_view_url, s3_is_enabled, upload_bytes_to_s3
from app.schemas.api import (
    ChecklistItemOut,
    SelectPathwayIn,
    StudentProfileIn,
    StudentProfileOut,
    StudentGoalIn,
    StudentGoalOut,
    StudentGoalUpdateIn,
    StudentGoalCheckInOut,
    StudentNotificationOut,
    StudentEngagementSummaryOut,
    UserPathwayOut,
)

router = APIRouter(prefix="/user")
ALLOWED_RESUME_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt", ".rtf"}
MAX_RESUME_FILE_SIZE_BYTES = 10 * 1024 * 1024


def _serialize_profile(profile: StudentProfile) -> dict:
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "semester": profile.semester,
        "state": profile.state,
        "university": profile.university,
        "masters_interest": profile.masters_interest,
        "masters_target": profile.masters_target,
        "masters_timeline": profile.masters_timeline,
        "masters_status": profile.masters_status,
        "resume_url": profile.resume_url,
        "resume_view_url": (
            resolve_file_view_url(profile.resume_url) if profile.resume_url else None
        ),
        "resume_filename": profile.resume_filename,
        "resume_uploaded_at": profile.resume_uploaded_at,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


def _serialize_goal(goal: StudentGoal) -> dict:
    return {
        "id": goal.id,
        "title": goal.title,
        "description": goal.description,
        "status": goal.status,
        "target_date": goal.target_date,
        "last_check_in_at": goal.last_check_in_at,
        "streak_days": goal.streak_days,
        "created_at": goal.created_at,
        "updated_at": goal.updated_at,
    }


def _serialize_notification(notification: StudentNotification) -> dict:
    return {
        "id": notification.id,
        "kind": notification.kind,
        "message": notification.message,
        "is_read": notification.is_read,
        "metadata": notification.metadata_json,
        "created_at": notification.created_at,
    }


@router.post("/pathway/select", response_model=UserPathwayOut)
def select_pathway(
    payload: SelectPathwayIn,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    cohort_id = payload.cohort_id
    cohort_label = payload.cohort
    if cohort_id and not cohort_label:
        cohort = db.query(Cohort).get(cohort_id)
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")
        cohort_label = cohort.name

    latest_version = (
        db.query(ChecklistVersion)
        .filter(ChecklistVersion.pathway_id == payload.pathway_id)
        .filter(ChecklistVersion.status == "published")
        .order_by(ChecklistVersion.version_number.desc())
        .first()
    )
    latest_version_id = latest_version.id if latest_version else None

    existing = db.query(UserPathway).filter(UserPathway.user_id == user_id).one_or_none()
    if existing:
        if (
            existing.major_id != payload.major_id
            or existing.pathway_id != payload.pathway_id
        ):
            raise HTTPException(status_code=409, detail="Pathway selection is locked")
        existing.major_id = payload.major_id
        existing.pathway_id = payload.pathway_id
        existing.cohort = cohort_label
        existing.cohort_id = cohort_id
        if latest_version_id:
            existing.checklist_version_id = latest_version_id
        existing.selected_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        try:
            sync_resume_requirement_matches(db, user_id)
        except Exception:
            logger.exception("sync_resume_requirement_matches failed for user %s", user_id)
        return existing

    record = UserPathway(
        user_id=user_id,
        major_id=payload.major_id,
        pathway_id=payload.pathway_id,
        cohort=cohort_label,
        cohort_id=cohort_id,
        checklist_version_id=latest_version_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    try:
        sync_resume_requirement_matches(db, user_id)
    except Exception:
        logger.exception("sync_resume_requirement_matches failed for user %s", user_id)
    return record


@router.get("/pathway", response_model=UserPathwayOut)
def get_pathway(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    record = db.query(UserPathway).filter(UserPathway.user_id == user_id).one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="No pathway selection found")
    if not record.checklist_version_id:
        version = (
            db.query(ChecklistVersion)
            .filter(ChecklistVersion.pathway_id == record.pathway_id)
            .filter(ChecklistVersion.status == "published")
            .order_by(ChecklistVersion.version_number.desc())
            .first()
        )
        if version:
            record.checklist_version_id = version.id
            db.commit()
            db.refresh(record)
    return record


@router.get("/checklist", response_model=list[ChecklistItemOut])
def get_checklist(
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
    proofs_by_item: dict[str, list[Proof]] = {}
    for proof in proofs:
        proofs_by_item.setdefault(str(proof.checklist_item_id), []).append(proof)

    results = []
    for item in items:
        item_proofs = proofs_by_item.get(str(item.id), [])
        verified = [p for p in item_proofs if p.status == "verified"]
        if verified:
            has_non_resume_verified = any(
                p.proof_type != RESUME_MATCH_PROOF_TYPE for p in verified
            )
            status = "complete" if has_non_resume_verified else "satisfied by resume upload"
        elif any(p.status == "submitted" for p in item_proofs):
            status = "waiting for verification"
        elif any(p.status == "needs_more_evidence" for p in item_proofs):
            status = "needs more evidence"
        elif any(p.status == "rejected" for p in item_proofs):
            status = "rejected"
        else:
            status = "incomplete"

        results.append(
            {
                "id": item.id,
                "title": item.title,
                "description": item.description,
                "tier": item.tier,
                "rationale": item.rationale,
                "is_critical": item.is_critical,
                "allowed_proof_types": item.allowed_proof_types or [],
                "status": status,
            }
        )
    return results


@router.get("/profile", response_model=StudentProfileOut)
def get_profile(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile found")
    return _serialize_profile(profile)


@router.put("/profile", response_model=StudentProfileOut)
def upsert_profile(
    payload: StudentProfileIn,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).one_or_none()
    if profile:
        profile.semester = payload.semester
        profile.state = payload.state
        profile.university = payload.university
        if payload.masters_interest is not None:
            profile.masters_interest = payload.masters_interest
        profile.masters_target = payload.masters_target
        profile.masters_timeline = payload.masters_timeline
        profile.masters_status = payload.masters_status
        profile.updated_at = datetime.utcnow()
    else:
        profile = StudentProfile(
            user_id=user_id,
            semester=payload.semester,
            state=payload.state,
            university=payload.university,
            masters_interest=payload.masters_interest or False,
            masters_target=payload.masters_target,
            masters_timeline=payload.masters_timeline,
            masters_status=payload.masters_status,
        )
        db.add(profile)
    db.commit()
    db.refresh(profile)
    return _serialize_profile(profile)


@router.post("/profile/resume", response_model=StudentProfileOut)
def upload_resume(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    original_name = os.path.basename(file.filename or "").strip()
    if not original_name:
        raise HTTPException(status_code=400, detail="Resume file is required")

    extension = Path(original_name).suffix.lower()
    if extension and extension not in ALLOWED_RESUME_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported resume file type. Use PDF, DOC, DOCX, TXT, or RTF.",
        )

    content = file.file.read(MAX_RESUME_FILE_SIZE_BYTES + 1)
    if len(content) > MAX_RESUME_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Resume file is too large (max 10MB).")

    content_type = file.content_type or "application/octet-stream"
    if s3_is_enabled():
        try:
            uploaded = upload_bytes_to_s3(
                user_id=user_id,
                filename=original_name,
                content_type=content_type,
                content=content,
                prefix="resumes",
            )
            resume_url = uploaded["file_url"]
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
    else:
        resume_dir = Path(settings.local_upload_dir) / "resumes" / user_id
        resume_dir.mkdir(parents=True, exist_ok=True)
        safe_name = original_name.replace(" ", "_")
        stored_name = f"{uuid4().hex}_{safe_name}"
        resume_path = resume_dir / stored_name
        with resume_path.open("wb") as handle:
            handle.write(content)
        resume_url = f"/uploads/resumes/{user_id}/{stored_name}"

    now = datetime.utcnow()

    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).one_or_none()
    if profile:
        profile.resume_url = resume_url
        profile.resume_filename = original_name
        profile.resume_uploaded_at = now
        profile.updated_at = now
    else:
        profile = StudentProfile(
            user_id=user_id,
            resume_url=resume_url,
            resume_filename=original_name,
            resume_uploaded_at=now,
            updated_at=now,
        )
        db.add(profile)

    db.commit()
    db.refresh(profile)
    try:
        sync_resume_requirement_matches(db, user_id)
    except Exception:
        logger.exception("sync_resume_requirement_matches failed for user %s", user_id)
    db.refresh(profile)
    return _serialize_profile(profile)


@router.get("/goals", response_model=list[StudentGoalOut])
def list_goals(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    goals = (
        db.query(StudentGoal)
        .filter(StudentGoal.user_id == user_id)
        .order_by(StudentGoal.updated_at.desc())
        .all()
    )
    return [_serialize_goal(goal) for goal in goals]


@router.post("/goals", response_model=StudentGoalOut)
def create_goal(
    payload: StudentGoalIn,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    now = datetime.utcnow()
    goal = StudentGoal(
        user_id=user_id,
        title=payload.title.strip(),
        description=payload.description,
        status="active",
        target_date=payload.target_date,
        created_at=now,
        updated_at=now,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return _serialize_goal(goal)


@router.put("/goals/{goal_id}", response_model=StudentGoalOut)
def update_goal(
    goal_id: str,
    payload: StudentGoalUpdateIn,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    goal = db.query(StudentGoal).get(goal_id)
    if not goal or goal.user_id != user_id:
        raise HTTPException(status_code=404, detail="Goal not found")
    data = payload.model_dump(exclude_unset=True)
    if "title" in data and data["title"] is not None:
        goal.title = str(data["title"]).strip()
    if "description" in data:
        goal.description = data["description"]
    if "status" in data and data["status"]:
        goal.status = str(data["status"])
    if "target_date" in data:
        goal.target_date = data["target_date"]
    goal.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(goal)
    return _serialize_goal(goal)


@router.post("/goals/{goal_id}/check-in", response_model=StudentGoalCheckInOut)
def goal_check_in(
    goal_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    goal = db.query(StudentGoal).get(goal_id)
    if not goal or goal.user_id != user_id:
        raise HTTPException(status_code=404, detail="Goal not found")

    now = datetime.utcnow()
    if goal.last_check_in_at:
        delta_days = (now.date() - goal.last_check_in_at.date()).days
        if delta_days == 0:
            streak = goal.streak_days
        elif delta_days == 1:
            streak = goal.streak_days + 1
        else:
            streak = 1
    else:
        streak = 1

    goal.last_check_in_at = now
    goal.streak_days = streak
    goal.updated_at = now
    db.commit()
    db.refresh(goal)
    return {
        "id": goal.id,
        "streak_days": goal.streak_days,
        "last_check_in_at": goal.last_check_in_at,
    }


@router.get("/notifications", response_model=list[StudentNotificationOut])
def list_notifications(
    unread_only: bool = False,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    query = db.query(StudentNotification).filter(StudentNotification.user_id == user_id)
    if unread_only:
        query = query.filter(StudentNotification.is_read.is_(False))
    rows = query.order_by(StudentNotification.created_at.desc()).limit(100).all()
    return [_serialize_notification(row) for row in rows]


@router.post("/notifications/generate", response_model=list[StudentNotificationOut])
def generate_notifications(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    now = datetime.utcnow()
    goals = (
        db.query(StudentGoal)
        .filter(StudentGoal.user_id == user_id)
        .filter(StudentGoal.status == "active")
        .all()
    )
    created: list[StudentNotification] = []
    for goal in goals:
        if goal.target_date:
            days_left = (goal.target_date.date() - now.date()).days
            if 0 <= days_left <= 7:
                note = StudentNotification(
                    user_id=user_id,
                    kind="deadline",
                    message=f"Goal '{goal.title}' is due in {days_left} day(s).",
                    metadata_json={"goal_id": str(goal.id), "days_left": days_left},
                    created_at=now,
                )
                db.add(note)
                created.append(note)
    if not created:
        note = StudentNotification(
            user_id=user_id,
            kind="nudge",
            message="Set a weekly goal and check in to build momentum.",
            metadata_json={},
            created_at=now,
        )
        db.add(note)
        created.append(note)
    db.commit()
    return [_serialize_notification(note) for note in created]


@router.post("/notifications/{notification_id}/read", response_model=StudentNotificationOut)
def mark_notification_read(
    notification_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    note = db.query(StudentNotification).get(notification_id)
    if not note or note.user_id != user_id:
        raise HTTPException(status_code=404, detail="Notification not found")
    note.is_read = True
    db.commit()
    db.refresh(note)
    return _serialize_notification(note)


@router.get("/engagement/summary", response_model=StudentEngagementSummaryOut)
def engagement_summary(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    goals = db.query(StudentGoal).filter(StudentGoal.user_id == user_id).all()
    notifications = (
        db.query(StudentNotification)
        .filter(StudentNotification.user_id == user_id)
        .all()
    )
    goals_total = len(goals)
    goals_completed = sum(1 for goal in goals if goal.status == "completed")
    active_streak_days = max([goal.streak_days for goal in goals], default=0)
    unread_notifications = sum(1 for note in notifications if not note.is_read)
    deadlines = []
    now = datetime.utcnow().date()
    for goal in goals:
        if goal.status != "active" or not goal.target_date:
            continue
        days_left = (goal.target_date.date() - now).days
        if days_left >= 0:
            deadlines.append((days_left, f"{goal.title} ({days_left}d left)"))
    deadlines.sort(key=lambda row: row[0])

    return {
        "goals_total": goals_total,
        "goals_completed": goals_completed,
        "active_streak_days": active_streak_days,
        "unread_notifications": unread_notifications,
        "next_deadlines": [label for _, label in deadlines[:5]],
    }
