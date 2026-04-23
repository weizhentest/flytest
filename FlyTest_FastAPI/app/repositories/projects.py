from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models.auth import User
from app.db.models.projects import Project, ProjectCredential, ProjectMember
from app.repositories.base import Repository


class ProjectRepository(Repository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def list_accessible_projects(self, *, user: User, search: str | None = None) -> list[Project]:
        stmt = (
            select(Project)
            .options(
                selectinload(Project.creator),
                selectinload(Project.credentials),
                selectinload(Project.members).selectinload(ProjectMember.user),
            )
        )
        if not user.is_superuser:
            stmt = stmt.join(ProjectMember, ProjectMember.project_id == Project.id).where(ProjectMember.user_id == user.id)
        if search:
            like = f"%{search}%"
            stmt = stmt.where((Project.name.ilike(like)) | (Project.description.ilike(like)))
        stmt = stmt.order_by(Project.created_at.desc())
        return list(self.db.scalars(stmt).unique().all())

    def get_project(self, *, project_id: int) -> Project | None:
        stmt = (
            select(Project)
            .where(Project.id == project_id)
            .options(
                selectinload(Project.creator),
                selectinload(Project.credentials),
                selectinload(Project.members).selectinload(ProjectMember.user),
            )
        )
        return self.db.scalar(stmt)

    def get_project_by_name(self, *, name: str) -> Project | None:
        return self.db.scalar(select(Project).where(Project.name == name))

    def get_user(self, *, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def get_platform_admins(self) -> list[User]:
        stmt = select(User).where((User.is_superuser.is_(True)) | (User.is_staff.is_(True)), User.is_active.is_(True))
        return list(self.db.scalars(stmt).all())

    def get_project_member(self, *, project_id: int, user_id: int) -> ProjectMember | None:
        stmt = select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
        return self.db.scalar(stmt)

    def list_project_members(self, *, project_id: int) -> list[ProjectMember]:
        stmt = (
            select(ProjectMember)
            .where(ProjectMember.project_id == project_id)
            .options(selectinload(ProjectMember.user))
            .order_by(ProjectMember.joined_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def create_project(self, project: Project) -> Project:
        self.db.add(project)
        self.db.flush()
        self.db.refresh(project)
        return project

    def add_member(self, member: ProjectMember) -> ProjectMember:
        self.db.add(member)
        self.db.flush()
        self.db.refresh(member)
        return member

    def add_credential(self, credential: ProjectCredential) -> ProjectCredential:
        self.db.add(credential)
        self.db.flush()
        self.db.refresh(credential)
        return credential

    def remove_project_credentials(self, *, project_id: int) -> None:
        for item in list(self.db.scalars(select(ProjectCredential).where(ProjectCredential.project_id == project_id)).all()):
            self.db.delete(item)
        self.db.flush()

    def delete_member(self, member: ProjectMember) -> None:
        self.db.delete(member)
        self.db.flush()

    def delete_project(self, project: Project) -> None:
        for member in list(self.db.scalars(select(ProjectMember).where(ProjectMember.project_id == project.id)).all()):
            self.db.delete(member)
        for credential in list(
            self.db.scalars(select(ProjectCredential).where(ProjectCredential.project_id == project.id)).all()
        ):
            self.db.delete(credential)
        self.db.delete(project)
        self.db.flush()
