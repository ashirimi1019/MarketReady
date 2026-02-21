"""Recruiter Truth-Link — public profile and shareable link generation."""
from __future__ import annotations
import secrets
import string
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user_id
from app.models.entities import (
    ChecklistItem, ChecklistVersion, Proof, StudentProfile, StudentAccount, UserPathway, CareerPathway
)
from app.api.routes.mri import compute_mri_components

router = APIRouter()


def _generate_slug(length: int = 10) -> str:
    """Generate a URL-safe random slug."""
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _get_verified_skills(db: Session, user_id: str) -> list[str]:
    """Get list of verified skill names for a user."""
    selection = db.query(UserPathway).filter(UserPathway.user_id == user_id).one_or_none()
    if not selection:
        return []
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
            return []
        version_id = version.id
    items = db.query(ChecklistItem).filter(ChecklistItem.version_id == version_id).all()
    proofs = db.query(Proof).filter(Proof.user_id == user_id).all()
    verified_ids = {str(p.checklist_item_id) for p in proofs if p.status == "verified"}
    return [i.title for i in items if str(i.id) in verified_ids]


def _get_public_profile_data(db: Session, user_id: str, username: str) -> dict[str, Any]:
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).one_or_none()
    selection = db.query(UserPathway).filter(UserPathway.user_id == user_id).one_or_none()

    pathway_name = None
    if selection:
        cp = db.query(CareerPathway).filter(CareerPathway.id == selection.pathway_id).first()
        if cp:
            pathway_name = cp.name

    mri_data = compute_mri_components(db, user_id)
    verified_skills = _get_verified_skills(db, user_id)

    # Count proofs by type
    proofs = db.query(Proof).filter(Proof.user_id == user_id, Proof.status == "verified").all()
    proof_count = len(proofs)

    github_username = (profile.github_username if profile else None)

    return {
        "username": username,
        "university": (profile.university if profile else None),
        "pathway": pathway_name,
        "mri_score": mri_data.get("score", 0.0),
        "mri_band": mri_data.get("band", "Not Started"),
        "mri_components": mri_data.get("components", {}),
        "verified_skills": verified_skills[:20],
        "proof_count": proof_count,
        "github_username": github_username,
        "github_audit_url": f"https://github.com/{github_username}" if github_username else None,
        "semester": (profile.semester if profile else None),
        "profile_generated_at": datetime.utcnow().isoformat(),
    }


@router.post("/profile/generate-share-link")
def generate_share_link(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Generate a unique shareable slug for the user's public profile."""
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).one_or_none()
    if not profile:
        # Create profile if it doesn't exist
        profile = StudentProfile(
            user_id=user_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(profile)

    # Generate unique slug
    if not profile.share_slug:
        for _ in range(10):
            slug = _generate_slug()
            existing = db.query(StudentProfile).filter(StudentProfile.share_slug == slug).first()
            if not existing:
                profile.share_slug = slug
                break
        else:
            raise HTTPException(status_code=500, detail="Could not generate unique share link")
    
    profile.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(profile)

    # Get account for username
    account = db.query(StudentAccount).filter(StudentAccount.username == user_id).first()
    username = account.username if account else user_id

    from app.core.config import settings
    share_url = f"{settings.public_app_base_url}/profile/{profile.share_slug}"

    return {
        "share_slug": profile.share_slug,
        "share_url": share_url,
        "username": username,
    }


@router.get("/public/{slug}")
def get_public_profile(slug: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Get a public profile by share slug or username."""
    # First try by share slug
    profile = db.query(StudentProfile).filter(StudentProfile.share_slug == slug).first()
    if profile:
        account = db.query(StudentAccount).filter(StudentAccount.username == profile.user_id).first()
        username = account.username if account else profile.user_id
        return _get_public_profile_data(db, profile.user_id, username)

    # Then try by username
    account = db.query(StudentAccount).filter(StudentAccount.username == slug).first()
    if account:
        return _get_public_profile_data(db, account.username, account.username)

    raise HTTPException(status_code=404, detail="Profile not found")
