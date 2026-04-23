from datetime import datetime
from datetime import timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models.auth import User
from app.db.models.mcp_tools import RemoteMCPConfig
from app.db.models.projects import Project, ProjectCredential, ProjectMember
from app.db.models.skills import Skill
from app.repositories.projects import ProjectRepository


ROLE_CHOICES = {"owner", "admin", "member"}


def _serialize_user_detail(user: User | None) -> dict | None:
    if not user:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email or "",
    }


def _serialize_credential(item: ProjectCredential) -> dict:
    return {
        "id": item.id,
        "system_url": item.system_url or "",
        "username": item.username or "",
        "password": None,
        "user_role": item.user_role or "",
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def _serialize_member(item: ProjectMember) -> dict:
    return {
        "id": item.id,
        "user": item.user_id,
        "user_detail": _serialize_user_detail(item.user),
        "role": item.role,
        "joined_at": item.joined_at.isoformat() if item.joined_at else "",
    }


def serialize_project(project: Project, *, include_members: bool = False) -> dict:
    payload = {
        "id": project.id,
        "name": project.name,
        "description": project.description or "",
        "creator": project.creator_id,
        "creator_detail": _serialize_user_detail(project.creator),
        "created_at": project.created_at.isoformat() if project.created_at else "",
        "updated_at": project.updated_at.isoformat() if project.updated_at else "",
        "credentials": [_serialize_credential(item) for item in (project.credentials or [])],
    }
    if include_members:
        payload["members"] = [_serialize_member(item) for item in (project.members or [])]
    return payload


def _ensure_project_access(project: Project, user: User) -> None:
    if user.is_superuser:
        return
    if any(member.user_id == user.id for member in (project.members or [])):
        return
    raise AppError("鎮ㄦ病鏈夋潈闄愯闂椤圭洰", status_code=403)


def _ensure_project_admin(project: Project, user: User) -> None:
    if user.is_superuser:
        return
    for member in project.members or []:
        if member.user_id == user.id and member.role in {"owner", "admin"}:
            return
    raise AppError("鎮ㄦ病鏈夎椤圭洰鐨勭鐞嗘潈闄?", status_code=403)


def _ensure_project_owner(project: Project, user: User) -> None:
    if user.is_superuser:
        return
    for member in project.members or []:
        if member.user_id == user.id and member.role == "owner":
            return
    raise AppError("鍙湁椤圭洰鎷ユ湁鑰呭彲浠ユ墽琛岃鎿嶄綔", status_code=403)


def list_projects(db: Session, *, user: User, search: str | None = None) -> list[dict]:
    projects = ProjectRepository(db).list_accessible_projects(user=user, search=search)
    return [serialize_project(item, include_members=False) for item in projects]


def get_project_detail(db: Session, *, user: User, project_id: int) -> dict:
    repo = ProjectRepository(db)
    project = repo.get_project(project_id=project_id)
    if not project:
        raise AppError("椤圭洰涓嶅瓨鍦?", status_code=404)
    _ensure_project_access(project, user)
    return serialize_project(project, include_members=True)


def create_project(db: Session, *, user: User, payload: dict) -> dict:
    repo = ProjectRepository(db)
    name = str(payload.get("name") or "").strip()
    if not name:
        raise AppError("椤圭洰鍚嶇О涓嶈兘涓虹┖", status_code=400, errors={"name": ["椤圭洰鍚嶇О涓嶈兘涓虹┖"]})
    if repo.get_project_by_name(name=name):
        raise AppError("椤圭洰鍚嶇О宸插瓨鍦?", status_code=400, errors={"name": ["椤圭洰鍚嶇О宸插瓨鍦?"]})

    project = Project(
        name=name,
        description=str(payload.get("description") or "").strip(),
        creator_id=user.id,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    repo.create_project(project)

    repo.add_member(
        ProjectMember(
            project_id=project.id,
            user_id=user.id,
            role="owner",
            joined_at=datetime.now(),
        )
    )

    for admin in repo.get_platform_admins():
        if admin.id == user.id:
            continue
        if repo.get_project_member(project_id=project.id, user_id=admin.id):
            continue
        repo.add_member(
            ProjectMember(
                project_id=project.id,
                user_id=admin.id,
                role="admin",
                joined_at=datetime.now(),
            )
        )

    for item in payload.get("credentials") or []:
        repo.add_credential(
            ProjectCredential(
                project_id=project.id,
                system_url=str(item.get("system_url") or ""),
                username=str(item.get("username") or ""),
                password=str(item.get("password") or ""),
                user_role=str(item.get("user_role") or ""),
                created_at=datetime.now(),
            )
        )

    db.commit()
    project = repo.get_project(project_id=project.id)
    return serialize_project(project, include_members=True)


def update_project(db: Session, *, user: User, project_id: int, payload: dict) -> dict:
    repo = ProjectRepository(db)
    project = repo.get_project(project_id=project_id)
    if not project:
        raise AppError("椤圭洰涓嶅瓨鍦?", status_code=404)
    _ensure_project_admin(project, user)

    if "name" in payload and payload.get("name") is not None:
        name = str(payload.get("name") or "").strip()
        if not name:
            raise AppError("椤圭洰鍚嶇О涓嶈兘涓虹┖", status_code=400, errors={"name": ["椤圭洰鍚嶇О涓嶈兘涓虹┖"]})
        existing = repo.get_project_by_name(name=name)
        if existing and existing.id != project.id:
            raise AppError("椤圭洰鍚嶇О宸插瓨鍦?", status_code=400, errors={"name": ["椤圭洰鍚嶇О宸插瓨鍦?"]})
        project.name = name
    if "description" in payload and payload.get("description") is not None:
        project.description = str(payload.get("description") or "")
    project.updated_at = datetime.now()
    db.add(project)

    if "credentials" in payload and payload.get("credentials") is not None:
        repo.remove_project_credentials(project_id=project.id)
        for item in payload.get("credentials") or []:
            repo.add_credential(
                ProjectCredential(
                    project_id=project.id,
                    system_url=str(item.get("system_url") or ""),
                    username=str(item.get("username") or ""),
                    password=str(item.get("password") or ""),
                    user_role=str(item.get("user_role") or ""),
                    created_at=datetime.now(),
                )
            )

    db.commit()
    project = repo.get_project(project_id=project.id)
    return serialize_project(project, include_members=True)


def delete_project(db: Session, *, user: User, project_id: int) -> None:
    repo = ProjectRepository(db)
    project = repo.get_project(project_id=project_id)
    if not project:
        raise AppError("椤圭洰涓嶅瓨鍦?", status_code=404)
    _ensure_project_owner(project, user)
    repo.delete_project(project)
    db.commit()


def list_project_members(db: Session, *, user: User, project_id: int) -> list[dict]:
    repo = ProjectRepository(db)
    project = repo.get_project(project_id=project_id)
    if not project:
        raise AppError("椤圭洰涓嶅瓨鍦?", status_code=404)
    _ensure_project_access(project, user)
    return [_serialize_member(item) for item in repo.list_project_members(project_id=project_id)]


def add_project_member(db: Session, *, user: User, project_id: int, payload: dict) -> dict:
    repo = ProjectRepository(db)
    project = repo.get_project(project_id=project_id)
    if not project:
        raise AppError("椤圭洰涓嶅瓨鍦?", status_code=404)
    _ensure_project_admin(project, user)

    user_id = int(payload.get("user_id") or 0)
    role = str(payload.get("role") or "member")
    if role not in ROLE_CHOICES:
        raise AppError("鏃犳晥鐨勮鑹?", status_code=400)
    target_user = repo.get_user(user_id=user_id)
    if not target_user:
        raise AppError("鐢ㄦ埛涓嶅瓨鍦?", status_code=400)
    if repo.get_project_member(project_id=project_id, user_id=user_id):
        raise AppError("璇ョ敤鎴峰凡缁忔槸椤圭洰鎴愬憳", status_code=400)

    repo.add_member(
        ProjectMember(
            project_id=project_id,
            user_id=user_id,
            role=role,
            joined_at=datetime.now(),
        )
    )
    db.commit()
    member = repo.get_project_member(project_id=project_id, user_id=user_id)
    return _serialize_member(member)


def remove_project_member(db: Session, *, user: User, project_id: int, target_user_id: int) -> None:
    repo = ProjectRepository(db)
    project = repo.get_project(project_id=project_id)
    if not project:
        raise AppError("椤圭洰涓嶅瓨鍦?", status_code=404)
    _ensure_project_admin(project, user)
    member = repo.get_project_member(project_id=project_id, user_id=target_user_id)
    if not member:
        raise AppError("鎴愬憳涓嶅瓨鍦?", status_code=404)
    if member.role == "owner" and not user.is_superuser:
        raise AppError("涓嶈兘绉婚櫎椤圭洰鎷ユ湁鑰?", status_code=403)
    if member.user_id == user.id and not user.is_superuser:
        raise AppError("涓嶈兘绉婚櫎鑷繁", status_code=403)
    repo.delete_member(member)
    db.commit()


def update_project_member_role(db: Session, *, user: User, project_id: int, payload: dict) -> dict:
    repo = ProjectRepository(db)
    project = repo.get_project(project_id=project_id)
    if not project:
        raise AppError("椤圭洰涓嶅瓨鍦?", status_code=404)
    _ensure_project_admin(project, user)

    user_id = int(payload.get("user_id") or 0)
    role = str(payload.get("role") or "")
    if role not in ROLE_CHOICES:
        raise AppError("鏃犳晥鐨勮鑹?", status_code=400)
    member = repo.get_project_member(project_id=project_id, user_id=user_id)
    if not member:
        raise AppError("鎴愬憳涓嶅瓨鍦?", status_code=404)
    if member.role == "owner" and not (
        user.is_superuser or any(item.user_id == user.id and item.role == "owner" for item in project.members or [])
    ):
        raise AppError("鍙湁椤圭洰鎷ユ湁鑰呮垨瓒呯骇绠＄悊鍛樺彲浠ヤ慨鏀规嫢鏈夎€呰鑹?", status_code=403)
    if member.user_id == user.id and not user.is_superuser:
        raise AppError("涓嶈兘淇敼鑷繁鐨勮鑹?", status_code=403)

    if role == "owner":
        for item in project.members or []:
            if item.role == "owner" and item.user_id != user_id:
                item.role = "admin"
                self_member = repo.get_project_member(project_id=project_id, user_id=item.user_id)
                if self_member:
                    self_member.role = "admin"
                    db.add(self_member)

    member.role = role
    db.add(member)
    db.commit()
    member = repo.get_project_member(project_id=project_id, user_id=user_id)
    return _serialize_member(member)


def _coerce_dt(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def get_project_statistics(*, db: Session, user: User, project_id: int) -> dict:
    repo = ProjectRepository(db)
    project = repo.get_project(project_id=project_id)
    if not project:
        raise AppError("椤圭洰涓嶅瓨鍦?", status_code=404)
    _ensure_project_access(project, user)

    testcase_row = db.execute(
        text(
            """
            SELECT
              COUNT(*) AS total,
              SUM(CASE WHEN review_status = 'pending_review' THEN 1 ELSE 0 END) AS pending_review,
              SUM(CASE WHEN review_status = 'approved' THEN 1 ELSE 0 END) AS approved,
              SUM(CASE WHEN review_status = 'needs_optimization' THEN 1 ELSE 0 END) AS needs_optimization,
              SUM(CASE WHEN review_status = 'optimization_pending_review' THEN 1 ELSE 0 END) AS optimization_pending_review,
              SUM(CASE WHEN review_status = 'unavailable' THEN 1 ELSE 0 END) AS unavailable
            FROM testcases_testcase
            WHERE project_id = :project_id
            """
        ),
        {"project_id": project_id},
    ).mappings().one()

    execution_rows = db.execute(
        text(
            """
            SELECT
              e.status,
              e.passed_count,
              e.failed_count,
              e.skipped_count,
              e.error_count,
              e.total_count,
              e.created_at
            FROM testcases_testexecution e
            JOIN testcases_testsuite s ON s.id = e.suite_id
            WHERE s.project_id = :project_id
            """
        ),
        {"project_id": project_id},
    ).mappings().all()

    total_executions = len(execution_rows)
    total_completed = sum(1 for row in execution_rows if row["status"] == "completed")
    total_failed = sum(1 for row in execution_rows if row["status"] == "failed")
    total_cancelled = sum(1 for row in execution_rows if row["status"] == "cancelled")
    total_passed_cases = sum(int(row["passed_count"] or 0) for row in execution_rows)
    total_failed_cases = sum(int(row["failed_count"] or 0) for row in execution_rows)
    total_skipped_cases = sum(int(row["skipped_count"] or 0) for row in execution_rows)
    total_error_cases = sum(int(row["error_count"] or 0) for row in execution_rows)
    total_cases = sum(int(row["total_count"] or 0) for row in execution_rows)

    now = datetime.now()
    thirty_days_ago = now - timedelta(days=30)
    daily_stats_7d = []
    for i in range(7):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        day_items = []
        for row in execution_rows:
            created_at = _coerce_dt(row["created_at"])
            if created_at and day_start <= created_at.replace(tzinfo=None) < day_end:
                day_items.append(row)
        daily_stats_7d.append(
            {
                "date": day_start.strftime("%Y-%m-%d"),
                "execution_count": len(day_items),
                "passed": sum(int(item["passed_count"] or 0) for item in day_items),
                "failed": sum(int(item["failed_count"] or 0) for item in day_items),
            }
        )
    daily_stats_7d.reverse()

    stats_30d_items = []
    for row in execution_rows:
        created_at = _coerce_dt(row["created_at"])
        if created_at and created_at.replace(tzinfo=None) >= thirty_days_ago:
            stats_30d_items.append(row)

    mcp_stats = {
        "total": db.query(RemoteMCPConfig).count(),
        "active": db.query(RemoteMCPConfig).filter(RemoteMCPConfig.is_active.is_(True)).count(),
    }
    skill_stats = {
        "total": db.query(Skill).count(),
        "active": db.query(Skill).filter(Skill.is_active.is_(True)).count(),
    }

    ui_testcases_total = db.execute(
        text("SELECT COUNT(*) AS total FROM ui_test_case WHERE project_id = :project_id"),
        {"project_id": project_id},
    ).mappings().one()["total"] or 0
    ui_execution_rows = db.execute(
        text(
            """
            SELECT status
            FROM ui_execution_record
            WHERE test_case_id IN (
              SELECT id FROM ui_test_case WHERE project_id = :project_id
            )
            """
        ),
        {"project_id": project_id},
    ).mappings().all()
    ui_automation_stats = {
        "total_cases": int(ui_testcases_total),
        "total_executions": len(ui_execution_rows),
        "by_status": {
            "success": sum(1 for row in ui_execution_rows if row["status"] == 2),
            "failed": sum(1 for row in ui_execution_rows if row["status"] == 3),
            "cancelled": sum(1 for row in ui_execution_rows if row["status"] == 4),
        },
    }

    return {
        "project": {
            "id": project.id,
            "name": project.name,
        },
        "testcases": {
            "total": int(testcase_row["total"] or 0),
            "by_review_status": {
                "pending_review": int(testcase_row["pending_review"] or 0),
                "approved": int(testcase_row["approved"] or 0),
                "needs_optimization": int(testcase_row["needs_optimization"] or 0),
                "optimization_pending_review": int(testcase_row["optimization_pending_review"] or 0),
                "unavailable": int(testcase_row["unavailable"] or 0),
            },
        },
        "executions": {
            "total_executions": total_executions,
            "by_status": {
                "completed": total_completed,
                "failed": total_failed,
                "cancelled": total_cancelled,
            },
            "case_results": {
                "total": total_cases,
                "passed": total_passed_cases,
                "failed": total_failed_cases,
                "skipped": total_skipped_cases,
                "error": total_error_cases,
            },
        },
        "execution_trend": {
            "daily_7d": daily_stats_7d,
            "summary_30d": {
                "execution_count": len(stats_30d_items),
                "passed": sum(int(item["passed_count"] or 0) for item in stats_30d_items),
                "failed": sum(int(item["failed_count"] or 0) for item in stats_30d_items),
            },
        },
        "mcp": mcp_stats,
        "skills": skill_stats,
        "ui_automation": ui_automation_stats,
    }
