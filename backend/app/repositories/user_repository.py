"""Database queries for users."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def list(self) -> list[User]:
        return list(self.db.scalars(select(User).order_by(User.username)))

    def get_by_username(self, username: str) -> User | None:
        return self.db.scalar(select(User).where(User.username == username))

    def create(self, values: dict[str, object]) -> User:
        entity = User(**values)
        self.db.add(entity)
        self.db.flush()
        return entity

    def update(self, entity: User, values: dict[str, object]) -> User:
        for field, value in values.items():
            setattr(entity, field, value)
        self.db.flush()
        return entity

    def deactivate(self, entity: User) -> User:
        entity.is_active = False
        self.db.flush()
        return entity
