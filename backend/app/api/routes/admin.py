from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.models.entities import (
    CareerPathway,
    Skill,
    ChecklistVersion,
    ChecklistItem,
    ChecklistChangeLog,
    Milestone,
    Proof,
)
from app.schemas.api import (
    AdminPathwayIn,
    AdminPathwayOut,
    AdminSkillIn,
    AdminSkillOut,
    AdminSkillUpdateIn,
    AdminChecklistDraftIn,
    AdminChecklistDraftOut,
    AdminChecklistVersionOut,
    AdminChecklistItemOut,
    AdminChecklistItemUpdateIn,
    AdminPublishOut,
    AdminMilestoneIn,
    AdminMilestoneOut,
    AdminProofVerifyIn,
    AdminProofVerifyOut,
    AdminProofOut,
    AdminProofUpdateIn,
    ChecklistChangeLogOut,
)
from app.services.storage import resolve_file_view_url

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])


@router.post("/pathways", response_model=AdminPathwayOut)
def upsert_pathway(payload: AdminPathwayIn, db: Session = Depends(get_db)):
    existing = db.query(CareerPathway).filter(CareerPathway.name == payload.name).one_or_none()
    if existing:
        existing.description = payload.description
        existing.is_active = payload.is_active
        db.commit()
        db.refresh(existing)
        return existing

    pathway = CareerPathway(
        name=payload.name,
        description=payload.description,
        is_active=payload.is_active,
    )
    db.add(pathway)
    db.commit()
    db.refresh(pathway)
    return pathway


@router.post("/skills", response_model=AdminSkillOut)
def upsert_skill(payload: AdminSkillIn, db: Session = Depends(get_db)):
    existing = db.query(Skill).filter(Skill.name == payload.name).one_or_none()
    if existing:
        existing.description = payload.description
        db.commit()
        db.refresh(existing)
        return existing

    skill = Skill(name=payload.name, description=payload.description)
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return skill


@router.get("/skills", response_model=list[AdminSkillOut])
def list_skills(db: Session = Depends(get_db)):
    return db.query(Skill).order_by(Skill.name.asc()).all()


@router.put("/skills/{skill_id}", response_model=AdminSkillOut)
def update_skill(skill_id: str, payload: AdminSkillUpdateIn, db: Session = Depends(get_db)):
    skill = db.query(Skill).get(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        skill.name = data["name"]
    if "description" in data:
        skill.description = data["description"]

    db.commit()
    db.refresh(skill)
    return skill


@router.delete("/skills/{skill_id}")
def delete_skill(skill_id: str, db: Session = Depends(get_db)):
    skill = db.query(Skill).get(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    db.delete(skill)
    db.commit()
    return {"deleted": True, "id": skill_id}


@router.post("/checklists/{pathway_id}/draft", response_model=AdminChecklistDraftOut)
def create_draft_checklist(
    pathway_id: str,
    payload: AdminChecklistDraftIn,
    db: Session = Depends(get_db),
):
    pathway = db.query(CareerPathway).get(pathway_id)
    if not pathway:
        raise HTTPException(status_code=404, detail="Pathway not found")

    latest_version = (
        db.query(func.max(ChecklistVersion.version_number))
        .filter(ChecklistVersion.pathway_id == pathway_id)
        .scalar()
        or 0
    )
    version = ChecklistVersion(
        pathway_id=pathway_id,
        version_number=int(latest_version) + 1,
        status="draft",
    )
    db.add(version)
    db.flush()

    item_count = 0
    for item in payload.items:
        skill_id = item.skill_id
        if not skill_id and item.skill_name:
            skill = db.query(Skill).filter(Skill.name == item.skill_name).one_or_none()
            if not skill:
                skill = Skill(name=item.skill_name)
                db.add(skill)
                db.flush()
            skill_id = skill.id

        checklist_item = ChecklistItem(
            version_id=version.id,
            skill_id=skill_id,
            title=item.title,
            description=item.description,
            tier=item.tier,
            rationale=item.rationale,
            is_critical=item.is_critical,
            allowed_proof_types=item.allowed_proof_types,
        )
        db.add(checklist_item)
        item_count += 1

    db.commit()
    return {
        "version_id": version.id,
        "version_number": version.version_number,
        "status": version.status,
        "item_count": item_count,
    }


@router.get("/checklists/{pathway_id}/versions", response_model=list[AdminChecklistVersionOut])
def list_checklist_versions(pathway_id: str, db: Session = Depends(get_db)):
    versions = (
        db.query(ChecklistVersion)
        .filter(ChecklistVersion.pathway_id == pathway_id)
        .order_by(ChecklistVersion.version_number.desc())
        .all()
    )
    results = []
    for version in versions:
        item_count = (
            db.query(func.count(ChecklistItem.id))
            .filter(ChecklistItem.version_id == version.id)
            .scalar()
            or 0
        )
        results.append(
            {
                "id": version.id,
                "pathway_id": version.pathway_id,
                "version_number": version.version_number,
                "status": version.status,
                "published_at": version.published_at,
                "item_count": item_count,
            }
        )
    return results


@router.get("/checklists/versions/{version_id}/items", response_model=list[AdminChecklistItemOut])
def list_checklist_items(version_id: str, db: Session = Depends(get_db)):
    return (
        db.query(ChecklistItem)
        .filter(ChecklistItem.version_id == version_id)
        .order_by(ChecklistItem.title.asc())
        .all()
    )


@router.put("/checklists/items/{item_id}", response_model=AdminChecklistItemOut)
def update_checklist_item(
    item_id: str,
    payload: AdminChecklistItemUpdateIn,
    db: Session = Depends(get_db),
):
    item = db.query(ChecklistItem).get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Checklist item not found")

    data = payload.model_dump(exclude_unset=True)
    for field in [
        "title",
        "description",
        "tier",
        "rationale",
        "is_critical",
        "allowed_proof_types",
        "skill_id",
    ]:
        if field in data:
            setattr(item, field, data[field])

    db.commit()
    db.refresh(item)
    return item


@router.delete("/checklists/items/{item_id}")
def delete_checklist_item(item_id: str, db: Session = Depends(get_db)):
    item = db.query(ChecklistItem).get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Checklist item not found")
    db.delete(item)
    db.commit()
    return {"deleted": True, "id": item_id}


@router.post("/checklists/{pathway_id}/publish", response_model=AdminPublishOut)
def publish_checklist(pathway_id: str, db: Session = Depends(get_db)):
    draft = (
        db.query(ChecklistVersion)
        .filter(ChecklistVersion.pathway_id == pathway_id)
        .filter(ChecklistVersion.status == "draft")
        .order_by(ChecklistVersion.version_number.desc())
        .first()
    )
    if not draft:
        raise HTTPException(status_code=404, detail="No draft checklist found")

    db.query(ChecklistVersion).filter(ChecklistVersion.pathway_id == pathway_id).filter(
        ChecklistVersion.status == "published"
    ).update({"status": "archived"})
    previous_published = (
        db.query(ChecklistVersion)
        .filter(ChecklistVersion.pathway_id == pathway_id)
        .filter(ChecklistVersion.status == "archived")
        .order_by(ChecklistVersion.version_number.desc())
        .first()
    )

    draft.status = "published"
    draft.published_at = datetime.utcnow()
    db.add(
        ChecklistChangeLog(
            pathway_id=pathway_id,
            from_version_id=previous_published.id if previous_published else None,
            to_version_id=draft.id,
            change_type="publish",
            summary=f"Published checklist version {draft.version_number}.",
            metadata_json={"version_number": draft.version_number},
            created_by="admin",
            created_at=datetime.utcnow(),
        )
    )
    db.commit()
    db.refresh(draft)
    return {
        "version_id": draft.id,
        "status": draft.status,
        "published_at": draft.published_at,
    }


@router.post("/checklists/{pathway_id}/rollback", response_model=AdminPublishOut)
def rollback_checklist(pathway_id: str, db: Session = Depends(get_db)):
    current = (
        db.query(ChecklistVersion)
        .filter(ChecklistVersion.pathway_id == pathway_id)
        .filter(ChecklistVersion.status == "published")
        .order_by(ChecklistVersion.version_number.desc())
        .first()
    )
    target = (
        db.query(ChecklistVersion)
        .filter(ChecklistVersion.pathway_id == pathway_id)
        .filter(ChecklistVersion.status == "archived")
        .order_by(ChecklistVersion.version_number.desc())
        .first()
    )
    if not current or not target:
        raise HTTPException(status_code=404, detail="No rollback target available")

    current.status = "archived"
    target.status = "published"
    target.published_at = datetime.utcnow()
    db.add(
        ChecklistChangeLog(
            pathway_id=pathway_id,
            from_version_id=current.id,
            to_version_id=target.id,
            change_type="rollback",
            summary=f"Rolled back from v{current.version_number} to v{target.version_number}.",
            metadata_json={
                "from_version_number": current.version_number,
                "to_version_number": target.version_number,
            },
            created_by="admin",
            created_at=datetime.utcnow(),
        )
    )
    db.commit()
    db.refresh(target)
    return {
        "version_id": target.id,
        "status": target.status,
        "published_at": target.published_at,
    }


@router.get("/checklists/{pathway_id}/changes", response_model=list[ChecklistChangeLogOut])
def list_checklist_changes(pathway_id: str, db: Session = Depends(get_db)):
    logs = (
        db.query(ChecklistChangeLog)
        .filter(ChecklistChangeLog.pathway_id == pathway_id)
        .order_by(ChecklistChangeLog.created_at.desc())
        .limit(200)
        .all()
    )
    return [
        {
            "id": log.id,
            "pathway_id": log.pathway_id,
            "from_version_id": log.from_version_id,
            "to_version_id": log.to_version_id,
            "change_type": log.change_type,
            "summary": log.summary,
            "metadata": log.metadata_json,
            "created_by": log.created_by,
            "created_at": log.created_at,
        }
        for log in logs
    ]


@router.post("/milestones", response_model=AdminMilestoneOut)
def create_milestone(payload: AdminMilestoneIn, db: Session = Depends(get_db)):
    existing = (
        db.query(Milestone)
        .filter(Milestone.pathway_id == payload.pathway_id)
        .filter(Milestone.semester_index == payload.semester_index)
        .filter(Milestone.title == payload.title)
        .one_or_none()
    )
    if existing:
        return {
            "milestone_id": existing.id,
            "pathway_id": existing.pathway_id,
            "title": existing.title,
            "description": existing.description,
            "semester_index": existing.semester_index,
        }

    milestone = Milestone(
        pathway_id=payload.pathway_id,
        title=payload.title,
        description=payload.description,
        semester_index=payload.semester_index,
    )
    db.add(milestone)
    db.commit()
    db.refresh(milestone)
    return {
        "milestone_id": milestone.id,
        "pathway_id": milestone.pathway_id,
        "title": milestone.title,
        "description": milestone.description,
        "semester_index": milestone.semester_index,
    }


@router.post("/proofs/{proof_id}/verify", response_model=AdminProofVerifyOut)
def verify_proof(
    proof_id: str,
    payload: AdminProofVerifyIn,
    db: Session = Depends(get_db),
):
    proof = db.query(Proof).get(proof_id)
    if not proof:
        raise HTTPException(status_code=404, detail="Proof not found")

    status = payload.status.lower()
    if status not in {"verified", "rejected"}:
        raise HTTPException(status_code=400, detail="Invalid status")

    proof.status = status
    db.commit()
    db.refresh(proof)
    return {"id": proof.id, "status": proof.status}


@router.get("/proofs", response_model=list[AdminProofOut])
def list_proofs(
    status: str | None = None,
    user_id: str | None = None,
    checklist_item_id: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Proof)
    if status:
        query = query.filter(Proof.status == status)
    if user_id:
        query = query.filter(Proof.user_id == user_id)
    if checklist_item_id:
        query = query.filter(Proof.checklist_item_id == checklist_item_id)

    proofs = query.order_by(Proof.created_at.desc()).all()
    return [
        {
            "id": proof.id,
            "user_id": proof.user_id,
            "checklist_item_id": proof.checklist_item_id,
            "proof_type": proof.proof_type,
            "url": proof.url,
            "view_url": resolve_file_view_url(proof.url),
            "status": proof.status,
            "review_note": proof.review_note,
            "metadata": proof.metadata_json,
            "created_at": proof.created_at,
        }
        for proof in proofs
    ]


@router.put("/proofs/{proof_id}", response_model=AdminProofOut)
def update_proof(
    proof_id: str,
    payload: AdminProofUpdateIn,
    db: Session = Depends(get_db),
):
    proof = db.query(Proof).get(proof_id)
    if not proof:
        raise HTTPException(status_code=404, detail="Proof not found")

    data = payload.model_dump(exclude_unset=True)
    if "status" in data:
        proof.status = data["status"]
    if "url" in data:
        proof.url = data["url"]
    if "metadata" in data:
        proof.metadata_json = data["metadata"]
    if "review_note" in data:
        proof.review_note = data["review_note"]

    db.commit()
    db.refresh(proof)
    return {
        "id": proof.id,
        "user_id": proof.user_id,
        "checklist_item_id": proof.checklist_item_id,
        "proof_type": proof.proof_type,
        "url": proof.url,
        "view_url": resolve_file_view_url(proof.url),
        "status": proof.status,
        "review_note": proof.review_note,
        "metadata": proof.metadata_json,
        "created_at": proof.created_at,
    }


@router.delete("/proofs/{proof_id}")
def delete_proof(proof_id: str, db: Session = Depends(get_db)):
    proof = db.query(Proof).get(proof_id)
    if not proof:
        raise HTTPException(status_code=404, detail="Proof not found")
    db.delete(proof)
    db.commit()
    return {"deleted": True, "id": proof_id}
