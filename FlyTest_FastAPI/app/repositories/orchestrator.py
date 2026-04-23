from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models.orchestrator import OrchestratorTask
from app.repositories.base import Repository


class OrchestratorRepository(Repository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def list_tasks(self, *, user_id: int, project_id: int | None = None, status: str | None = None) -> list[OrchestratorTask]:
        stmt = (
            select(OrchestratorTask)
            .where(OrchestratorTask.user_id == user_id)
            .options(
                selectinload(OrchestratorTask.user),
                selectinload(OrchestratorTask.project),
            )
            .order_by(OrchestratorTask.created_at.desc(), OrchestratorTask.id.desc())
        )
        if project_id:
            stmt = stmt.where(OrchestratorTask.project_id == project_id)
        if status:
            stmt = stmt.where(OrchestratorTask.status == status)
        return list(self.db.scalars(stmt).all())

    def get_task(self, *, user_id: int, task_id: int) -> OrchestratorTask | None:
        stmt = (
            select(OrchestratorTask)
            .where(OrchestratorTask.id == task_id, OrchestratorTask.user_id == user_id)
            .options(
                selectinload(OrchestratorTask.user),
                selectinload(OrchestratorTask.project),
            )
        )
        return self.db.scalar(stmt)

    def create_task(self, task: OrchestratorTask) -> OrchestratorTask:
        self.db.add(task)
        self.db.flush()
        self.db.refresh(task)
        return task
