from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.auth import User
from app.db.models.projects import Project


class OrchestratorTask(Base):
    __tablename__ = "orchestrator_task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("auth_user.id"), nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects_project.id"), nullable=False)
    chat_session_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    requirement: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="pending")

    execution_plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    execution_history: Mapped[list] = mapped_column(JSON, default=list)
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    waiting_for: Mapped[str] = mapped_column(String(50), default="")
    user_notes: Mapped[str] = mapped_column(Text, default="")

    requirement_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    knowledge_docs: Mapped[list] = mapped_column(JSON, default=list)
    testcases: Mapped[list] = mapped_column(JSON, default=list)

    execution_log: Mapped[list] = mapped_column(JSON, default=list)
    error_message: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(lazy="selectin")
    project: Mapped[Project] = relationship(lazy="selectin")
