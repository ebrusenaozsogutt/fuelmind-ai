"""Business rules for users."""

from sqlalchemy.orm import Session

from app.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserUpdate
from app.utils.security import hash_password


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = UserRepository(db)

    def get(self, user_id: int) -> User:
        entity = self.repository.get(user_id)
        if entity is None:
            raise NotFoundError("User not found.")
        return entity

    def list(self) -> list[User]:
        return self.repository.list()

    def create(self, payload: UserCreate) -> User:
        if self.repository.get_by_username(payload.username):
            raise ConflictError("Username already exists.")
        values = payload.model_dump(exclude={"password"})
        values["password_hash"] = hash_password(payload.password)
        return self._commit(lambda: self.repository.create(values))

    def update(self, user_id: int, payload: UserUpdate, *, actor_id: int) -> User:
        entity = self.get(user_id)
        if entity.id == actor_id and payload.is_active is False:
            raise BusinessRuleError("You cannot deactivate your own account.")
        values = payload.model_dump(exclude_unset=True, exclude={"password"})
        if (
            payload.username
            and (existing := self.repository.get_by_username(payload.username))
            and existing.id != entity.id
        ):
            raise ConflictError("Username already exists.")
        if payload.password is not None:
            values["password_hash"] = hash_password(payload.password)
        return self._commit(lambda: self.repository.update(entity, values))

    def deactivate(self, user_id: int, *, actor_id: int) -> User:
        entity = self.get(user_id)
        if entity.id == actor_id:
            raise BusinessRuleError("You cannot deactivate your own account.")
        return self._commit(lambda: self.repository.deactivate(entity))

    def _commit(self, operation: object) -> User:
        try:
            entity = operation()  # type: ignore[operator]
            self.db.commit()
            self.db.refresh(entity)
            return entity
        except Exception:
            self.db.rollback()
            raise
