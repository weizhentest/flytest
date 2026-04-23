from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


user_groups = Table(
    "auth_user_groups",
    Base.metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", ForeignKey("auth_user.id"), nullable=False),
    Column("group_id", ForeignKey("auth_group.id"), nullable=False),
)

user_permissions = Table(
    "auth_user_user_permissions",
    Base.metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", ForeignKey("auth_user.id"), nullable=False),
    Column("permission_id", ForeignKey("auth_permission.id"), nullable=False),
)

group_permissions = Table(
    "auth_group_permissions",
    Base.metadata,
    Column("id", Integer, primary_key=True),
    Column("group_id", ForeignKey("auth_group.id"), nullable=False),
    Column("permission_id", ForeignKey("auth_permission.id"), nullable=False),
)


class Group(Base):
    __tablename__ = "auth_group"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    users: Mapped[list["User"]] = relationship(
        secondary=user_groups,
        lazy="selectin",
        overlaps="groups",
    )
    permissions: Mapped[list["Permission"]] = relationship(
        secondary=group_permissions,
        back_populates="groups",
        lazy="selectin",
    )


class ContentType(Base):
    __tablename__ = "django_content_type"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    app_label: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(100))


class Permission(Base):
    __tablename__ = "auth_permission"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    content_type_id: Mapped[int] = mapped_column(ForeignKey("django_content_type.id"))
    codename: Mapped[str] = mapped_column(String(100))
    content_type: Mapped[ContentType] = relationship(lazy="selectin")
    groups: Mapped[list[Group]] = relationship(
        secondary=group_permissions,
        back_populates="permissions",
        lazy="selectin",
    )


class User(Base):
    __tablename__ = "auth_user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    password: Mapped[str] = mapped_column(String(128))
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    username: Mapped[str] = mapped_column(String(150), unique=True)
    first_name: Mapped[str] = mapped_column(String(150), default="")
    last_name: Mapped[str] = mapped_column(String(150), default="")
    email: Mapped[str] = mapped_column(String(254), default="")
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    date_joined: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    groups: Mapped[list[Group]] = relationship(
        secondary=user_groups,
        lazy="selectin",
        overlaps="users",
    )
    direct_permissions: Mapped[list[Permission]] = relationship(
        secondary=user_permissions,
        lazy="selectin",
    )
