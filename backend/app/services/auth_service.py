"""Shared credential authentication service."""

from sqlalchemy.orm import Session

from app.exceptions import AuthenticationError, BusinessRuleError
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.utils.security import verify_password


class AuthService:
    """Authenticate users without exposing credential failure details."""

    def __init__(self, db: Session) -> None:
        self.repository = UserRepository(db)

    def authenticate(self, username: str, password: str) -> User:
        """Return the active user for valid credentials or a generic auth error."""

        user = self.repository.get_by_username(username)
        try:
            is_valid_password = user is not None and verify_password(
                password, user.password_hash
            )
        except BusinessRuleError:
            is_valid_password = False

        if user is None or not is_valid_password or not user.is_active:
            raise AuthenticationError("Invalid username or password.")
        return user
