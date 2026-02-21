"""Interactive 90-Day Pivot Kanban — CRUD + AI-generated plan."""
from __future__ import annotations
import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user_id
from app.models.entities import KanbanTask, StudentProfile, UserPathway
from app.services.ai import _call_llm, ai_is_configured
import json as _json

def _safe_json(text: str) -> dict | None:
    if not text:
        return None
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return _json.loads(text[start:end])
    except Exception:
        pass
    return None

router = APIRouter(prefix="/kanban")


class TaskCreateIn(BaseModel):
    title: str
    description: str | None = None
    status: str = "todo"
    week_number: int | None = None
    skill_tag: str | None = None
    priority: str = "medium"


class TaskUpdateIn(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    week_number: int | None = None
    skill_tag: str | None = None
    priority: str | None = None
    sort_order: int | None = None


def _serialize_task(task: KanbanTask) -> dict:
    return {
        "id": str(task.id),
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "week_number": task.week_number,
        "skill_tag": task.skill_tag,
        "priority": task.priority,
        "github_synced": task.github_synced,
        "ai_generated": task.ai_generated,
        "sort_order": task.sort_order,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


@router.get("/board")
def get_board(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    tasks = (
        db.query(KanbanTask)
        .filter(KanbanTask.user_id == user_id)
        .order_by(KanbanTask.sort_order.asc(), KanbanTask.created_at.asc())
        .all()
    )
    board = {"todo": [], "in_progress": [], "done": []}
    for task in tasks:
        col = task.status if task.status in board else "todo"
        board[col].append(_serialize_task(task))
    return {"board": board, "total": len(tasks)}


@router.post("/tasks")
def create_task(
    payload: TaskCreateIn,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    task = KanbanTask(
        user_id=user_id,
        title=payload.title.strip(),
        description=payload.description,
        status=payload.status,
        week_number=payload.week_number,
        skill_tag=payload.skill_tag,
        priority=payload.priority,
        sort_order=0,
        ai_generated=False,
        github_synced=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return _serialize_task(task)


@router.put("/tasks/{task_id}")
def update_task(
    task_id: str,
    payload: TaskUpdateIn,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    task = db.query(KanbanTask).filter(KanbanTask.id == task_id, KanbanTask.user_id == user_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if payload.title is not None:
        task.title = payload.title.strip()
    if payload.description is not None:
        task.description = payload.description
    if payload.status is not None:
        task.status = payload.status
    if payload.week_number is not None:
        task.week_number = payload.week_number
    if payload.skill_tag is not None:
        task.skill_tag = payload.skill_tag
    if payload.priority is not None:
        task.priority = payload.priority
    if payload.sort_order is not None:
        task.sort_order = payload.sort_order
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return _serialize_task(task)


@router.delete("/tasks/{task_id}")
def delete_task(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    task = db.query(KanbanTask).filter(KanbanTask.id == task_id, KanbanTask.user_id == user_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    return {"ok": True}


def _get_user_context(db: Session, user_id: str) -> dict:
    """Build context for AI plan generation."""
    from app.models.entities import (
        ChecklistItem, ChecklistVersion, Proof, StudentProfile, UserPathway as UPAlias, CareerPathway
    )
    selection = db.query(UPAlias).filter(UPAlias.user_id == user_id).one_or_none()
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).one_or_none()
    pathway_name = "Software Engineering"
    if selection:
        cp = db.query(CareerPathway).filter(CareerPathway.id == selection.pathway_id).first()
        if cp:
            pathway_name = cp.name

    gaps = []
    if selection:
        version_id = selection.checklist_version_id
        if not version_id:
            version = (
                db.query(ChecklistVersion)
                .filter(ChecklistVersion.pathway_id == selection.pathway_id)
                .filter(ChecklistVersion.status == "published")
                .order_by(ChecklistVersion.version_number.desc())
                .first()
            )
            if version:
                version_id = version.id
        if version_id:
            items = db.query(ChecklistItem).filter(ChecklistItem.version_id == version_id).all()
            proofs = db.query(Proof).filter(Proof.user_id == user_id).all()
            verified_ids = {str(p.checklist_item_id) for p in proofs if p.status == "verified"}
            gaps = [i.title for i in items if str(i.id) not in verified_ids and i.tier in ("non_negotiable", "strong_signal")][:8]

    return {
        "pathway": pathway_name,
        "gaps": gaps,
        "github_username": (profile.github_username if profile else None),
        "semester": (profile.semester if profile else None),
    }


@router.post("/generate")
def generate_ai_plan(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Generate an AI-powered 90-day pivot plan and populate the Kanban board."""
    # Remove old AI-generated tasks first
    db.query(KanbanTask).filter(
        KanbanTask.user_id == user_id,
        KanbanTask.ai_generated == True,
    ).delete()
    db.commit()

    context = _get_user_context(db, user_id)

    if ai_is_configured():
        system = (
            "You are a career coach creating a 90-day pivot plan. "
            "Given the student's skill gaps and pathway, create exactly 12 actionable tasks "
            "spread across 3 phases (weeks 1-4, 5-8, 9-12). "
            "Output JSON: {\"tasks\": [{\"title\": string, \"description\": string, \"week_number\": int, \"skill_tag\": string, \"priority\": \"high|medium|low\"}]}"
        )
        user_msg = json.dumps({
            "pathway": context["pathway"],
            "top_gaps": context["gaps"][:6],
            "github": bool(context["github_username"]),
        })
        try:
            raw = _call_llm(system, user_msg)
            parsed = _safe_json(raw)
            ai_tasks = parsed.get("tasks", []) if parsed else []
        except Exception:
            ai_tasks = []
    else:
        ai_tasks = []

    # Fallback: default 90-day plan if AI fails or not configured
    if not ai_tasks:
        ai_tasks = _default_90_day_plan(context["gaps"], context["pathway"])

    created = []
    for i, task_data in enumerate(ai_tasks[:12]):
        task = KanbanTask(
            user_id=user_id,
            title=str(task_data.get("title", "Untitled Task"))[:300],
            description=task_data.get("description"),
            status="todo",
            week_number=int(task_data.get("week_number", (i // 4) + 1)),
            skill_tag=task_data.get("skill_tag"),
            priority=task_data.get("priority", "medium"),
            sort_order=i,
            ai_generated=True,
            github_synced=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(task)
        created.append(task)

    db.commit()
    return {
        "tasks_created": len(created),
        "tasks": [_serialize_task(t) for t in created],
        "ai_powered": ai_is_configured() and bool(ai_tasks),
    }


def _default_90_day_plan(gaps: list[str], pathway: str) -> list[dict]:
    """Fallback 90-day plan when AI is unavailable."""
    phase1 = [
        {"title": f"Audit your current {pathway} skills", "description": "Review checklist and identify critical gaps", "week_number": 1, "skill_tag": "Planning", "priority": "high"},
        {"title": f"Close gap: {gaps[0]}" if gaps else "Complete first non-negotiable requirement", "description": "Focus on your #1 priority skill gap", "week_number": 2, "skill_tag": gaps[0] if gaps else "Core Skills", "priority": "high"},
        {"title": "Build a proof artifact for Week 2 skill", "description": "Create a project, get a certificate, or submit evidence", "week_number": 3, "skill_tag": "Evidence", "priority": "high"},
        {"title": f"Close gap: {gaps[1]}" if len(gaps) > 1 else "Improve GitHub profile quality", "description": "Add README to all repos, pin top 6 projects", "week_number": 4, "skill_tag": gaps[1] if len(gaps) > 1 else "GitHub", "priority": "medium"},
    ]
    phase2 = [
        {"title": "Complete a portfolio project (end-to-end)", "description": "Build something deployable that demonstrates your target role skills", "week_number": 5, "skill_tag": "Portfolio", "priority": "high"},
        {"title": f"Close gap: {gaps[2]}" if len(gaps) > 2 else "Add a cloud deployment to portfolio", "description": "Deploy to Vercel, AWS, or Railway", "week_number": 6, "skill_tag": gaps[2] if len(gaps) > 2 else "Cloud", "priority": "medium"},
        {"title": "Network: Attend 2 online tech events or meetups", "description": "LinkedIn connections + follow-up messages", "week_number": 7, "skill_tag": "Networking", "priority": "medium"},
        {"title": "Apply to 5 internships or entry-level positions", "description": "Tailor each application with your proof artifacts", "week_number": 8, "skill_tag": "Applications", "priority": "high"},
    ]
    phase3 = [
        {"title": f"Earn a certification: {pathway}", "description": "Complete an industry-recognized certificate to validate skills", "week_number": 9, "skill_tag": "Certification", "priority": "medium"},
        {"title": "Mock interview practice (3 sessions)", "description": "Use Interview AI or a peer to practice behavioral + technical", "week_number": 10, "skill_tag": "Interview Prep", "priority": "high"},
        {"title": "Update resume with all new proofs and projects", "description": "Ensure ATS keywords match your target roles", "week_number": 11, "skill_tag": "Resume", "priority": "medium"},
        {"title": "Final readiness check: run MRI score and address remaining gaps", "description": "Review MRI components and close final gaps before job search", "week_number": 12, "skill_tag": "Review", "priority": "high"},
    ]
    return phase1 + phase2 + phase3


@router.post("/sync-github")
def sync_github(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Auto-complete tasks based on GitHub activity."""
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).one_or_none()
    if not profile or not profile.github_username:
        raise HTTPException(status_code=400, detail="GitHub username not set in profile")

    import httpx
    from app.api.routes.github import _fetch_repos, HEADERS

    synced_count = 0
    try:
        with httpx.Client(timeout=10.0, headers=HEADERS, follow_redirects=True) as client:
            repos = _fetch_repos(client, profile.github_username)
            repo_names = {r.get("name", "").lower() for r in repos}
            languages = {(r.get("language") or "").lower() for r in repos}

        tasks = db.query(KanbanTask).filter(KanbanTask.user_id == user_id, KanbanTask.status != "done").all()
        for task in tasks:
            title_lower = task.title.lower()
            skill_lower = (task.skill_tag or "").lower()
            # Complete if skill tag matches a detected language or repo name
            if (
                any(lang in title_lower or lang in skill_lower for lang in languages if lang)
                or any(repo in title_lower for repo in repo_names if repo)
            ):
                task.status = "done"
                task.github_synced = True
                task.updated_at = datetime.utcnow()
                synced_count += 1
        db.commit()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GitHub sync error: {str(exc)[:200]}")

    return {"synced_count": synced_count}
