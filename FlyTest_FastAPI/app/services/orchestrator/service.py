from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models.auth import User
from app.db.models.orchestrator import OrchestratorTask
from app.db.models.projects import Project
from app.repositories.orchestrator import OrchestratorRepository


def _ensure_project_access(project: Project | None, user: User) -> Project:
    if not project:
        raise AppError("Project not found", status_code=404)
    if user.is_superuser:
        return project
    if any(member.user_id == user.id for member in (project.members or [])):
        return project
    raise AppError("Project not found", status_code=404)


def _serialize_task(task: OrchestratorTask) -> dict:
    return {
        "id": task.id,
        "user": task.user_id,
        "project": task.project_id,
        "requirement": task.requirement,
        "status": task.status,
        "requirement_analysis": task.requirement_analysis,
        "knowledge_docs": task.knowledge_docs or [],
        "testcases": task.testcases or [],
        "execution_log": task.execution_log or [],
        "error_message": task.error_message or "",
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


def list_tasks(*, db: Session, user: User, project: int | None = None, status: str | None = None) -> list[dict]:
    tasks = OrchestratorRepository(db).list_tasks(user_id=user.id, project_id=project, status=status)
    return [_serialize_task(item) for item in tasks]


def create_task(*, db: Session, user: User, payload: dict[str, Any]) -> dict:
    requirement = str(payload.get("requirement") or "").strip()
    project_id = int(payload.get("project") or 0)
    if not requirement:
        raise AppError("requirement is required", status_code=400)
    if not project_id:
        raise AppError("project is required", status_code=400)

    project_item = db.get(Project, project_id)
    project_item = _ensure_project_access(project_item, user)

    instance = OrchestratorRepository(db).create_task(
        OrchestratorTask(
            user_id=user.id,
            project_id=project_item.id,
            requirement=requirement,
            status="pending",
            user_notes=str(payload.get("user_notes") or ""),
            execution_history=[],
            knowledge_docs=[],
            testcases=[],
            execution_log=[],
            created_at=datetime.now(),
        )
    )
    db.commit()
    instance = OrchestratorRepository(db).get_task(user_id=user.id, task_id=instance.id)
    return _serialize_task(instance)


def get_task(*, db: Session, user: User, task_id: int) -> dict:
    instance = OrchestratorRepository(db).get_task(user_id=user.id, task_id=task_id)
    if not instance:
        raise AppError("Orchestrator task not found", status_code=404)
    return _serialize_task(instance)
