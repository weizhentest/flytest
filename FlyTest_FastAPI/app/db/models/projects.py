from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.auth import User


class Project(Base):
    __tablename__ = "projects_project"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    creator_id: Mapped[int | None] = mapped_column(ForeignKey("auth_user.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    creator: Mapped[User | None] = relationship(foreign_keys=[creator_id], lazy="selectin")
    members: Mapped[list["ProjectMember"]] = relationship(back_populates="project", lazy="selectin")
    credentials: Mapped[list["ProjectCredential"]] = relationship(back_populates="project", lazy="selectin")


class ProjectCredential(Base):
    __tablename__ = "projects_projectcredential"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects_project.id"))
    system_url: Mapped[str] = mapped_column(String(255), default="")
    username: Mapped[str] = mapped_column(String(100), default="")
    password: Mapped[str] = mapped_column(String(255), default="")
    user_role: Mapped[str] = mapped_column(String(50), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship(back_populates="credentials", lazy="selectin")


class ProjectMember(Base):
    __tablename__ = "projects_projectmember"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects_project.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("auth_user.id"))
    role: Mapped[str] = mapped_column(String(20), default="member")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship(back_populates="members", lazy="selectin")
    user: Mapped[User] = relationship(lazy="selectin")
