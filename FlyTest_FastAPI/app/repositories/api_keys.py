from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.api_keys import APIKey
from app.db.models.auth import User
from app.repositories.base import Repository


class APIKeyRepository(Repository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def list_keys(self, *, user: User) -> list[APIKey]:
        stmt = select(APIKey).where(APIKey.user_id == user.id).order_by(APIKey.created_at.desc())
        return list(self.db.scalars(stmt).all())

    def get_key(self, *, user: User, api_key_id: int) -> APIKey | None:
        stmt = select(APIKey).where(APIKey.user_id == user.id, APIKey.id == api_key_id)
        return self.db.scalar(stmt)

    def get_by_name(self, *, name: str) -> APIKey | None:
        stmt = select(APIKey).where(APIKey.name == name)
        return self.db.scalar(stmt)

    def create(self, api_key: APIKey) -> APIKey:
        self.db.add(api_key)
        self.db.flush()
        self.db.refresh(api_key)
        return api_key

    def delete(self, api_key: APIKey) -> None:
        self.db.delete(api_key)
        self.db.flush()
