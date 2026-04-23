from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models.skills import Skill
from app.repositories.base import Repository


class SkillsRepository(Repository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def list_skills(self, *, project_id: int) -> list[Skill]:
        stmt = (
            select(Skill)
            .where(Skill.project_id == project_id)
            .options(selectinload(Skill.project), selectinload(Skill.creator))
            .order_by(Skill.created_at.desc(), Skill.id.desc())
        )
        return list(self.db.scalars(stmt).all())

    def get_skill(self, *, project_id: int, skill_id: int) -> Skill | None:
        stmt = (
            select(Skill)
            .where(Skill.project_id == project_id, Skill.id == skill_id)
            .options(selectinload(Skill.project), selectinload(Skill.creator))
        )
        return self.db.scalar(stmt)

    def get_by_name(self, *, project_id: int, name: str) -> Skill | None:
        stmt = (
            select(Skill)
            .where(Skill.project_id == project_id, Skill.name == name)
            .options(selectinload(Skill.project), selectinload(Skill.creator))
        )
        return self.db.scalar(stmt)

    def create_skill(self, item: Skill) -> Skill:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item
