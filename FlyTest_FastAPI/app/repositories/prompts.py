from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models.prompts import UserPrompt
from app.repositories.base import Repository


class PromptRepository(Repository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def list_user_prompts(
        self,
        *,
        user_id: int,
        search: str | None = None,
        is_default: bool | None = None,
        is_active: bool | None = None,
        prompt_type: str | None = None,
        ordering: str | None = None,
    ) -> list[UserPrompt]:
        stmt = select(UserPrompt).where(UserPrompt.user_id == user_id)
        if search:
            like = f"%{search}%"
            stmt = stmt.where(or_(UserPrompt.name.ilike(like), UserPrompt.description.ilike(like)))
        if is_default is not None:
            stmt = stmt.where(UserPrompt.is_default == is_default)
        if is_active is not None:
            stmt = stmt.where(UserPrompt.is_active == is_active)
        if prompt_type:
            stmt = stmt.where(UserPrompt.prompt_type == prompt_type)

        if ordering == "name":
            stmt = stmt.order_by(UserPrompt.name.asc())
        elif ordering == "-name":
            stmt = stmt.order_by(UserPrompt.name.desc())
        elif ordering == "created_at":
            stmt = stmt.order_by(UserPrompt.created_at.asc())
        elif ordering == "-created_at":
            stmt = stmt.order_by(UserPrompt.created_at.desc())
        else:
            stmt = stmt.order_by(UserPrompt.updated_at.desc())
        return list(self.db.scalars(stmt).all())

    def get_by_id(self, *, user_id: int, prompt_id: int) -> UserPrompt | None:
        stmt = select(UserPrompt).where(UserPrompt.user_id == user_id, UserPrompt.id == prompt_id)
        return self.db.scalar(stmt)

    def get_default(self, *, user_id: int) -> UserPrompt | None:
        stmt = select(UserPrompt).where(
            UserPrompt.user_id == user_id,
            UserPrompt.prompt_type == "general",
            UserPrompt.is_default.is_(True),
            UserPrompt.is_active.is_(True),
        )
        return self.db.scalar(stmt)

    def get_by_type(self, *, user_id: int, prompt_type: str) -> UserPrompt | None:
        stmt = select(UserPrompt).where(
            UserPrompt.user_id == user_id,
            UserPrompt.prompt_type == prompt_type,
            UserPrompt.is_active.is_(True),
        )
        return self.db.scalar(stmt)

    def find_by_name(self, *, user_id: int, name: str) -> UserPrompt | None:
        stmt = select(UserPrompt).where(UserPrompt.user_id == user_id, UserPrompt.name == name)
        return self.db.scalar(stmt)

    def create(self, prompt: UserPrompt) -> UserPrompt:
        self.db.add(prompt)
        self.db.flush()
        self.db.refresh(prompt)
        return prompt

    def delete(self, prompt: UserPrompt) -> None:
        self.db.delete(prompt)
        self.db.flush()
