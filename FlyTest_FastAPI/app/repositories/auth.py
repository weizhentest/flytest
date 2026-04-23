from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.auth import User
from app.repositories.base import Repository


class AuthRepository(Repository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_user_by_username(self, username: str) -> User | None:
        return self.db.scalar(select(User).where(User.username == username))

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)
