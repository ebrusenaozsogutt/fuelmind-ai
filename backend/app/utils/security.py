"""Password hashing and JWT helpers."""

from datetime import datetime, timedelta, timezone
from typing import Any

from passlib.context import CryptContext
from jose import jwt

from app.config import settings
from app.exceptions import BusinessRuleError
from app.utils.enums import UserRole


_password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_BCRYPT_MAX_PASSWORD_BYTES = 72
_MIN_PASSWORD_CHARACTERS = 8
JWT_ALGORITHM = "HS256"


def _validate_password(password: str) -> None:
    """Validate raw password input without mutating or truncating it."""

    if not password:
        raise BusinessRuleError("Password cannot be empty.")
    if len(password) < _MIN_PASSWORD_CHARACTERS:
        raise BusinessRuleError("Password must be at least 8 characters long.")
    if len(password.encode("utf-8")) > _BCRYPT_MAX_PASSWORD_BYTES:
        raise BusinessRuleError("Password must not exceed 72 bytes when UTF-8 encoded.")


def hash_password(password: str) -> str:
    """Return a bcrypt password hash; never persist the raw password."""

    _validate_password(password)
    return _password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a raw password against its persisted hash."""

    _validate_password(password)
    return _password_context.verify(password, password_hash)


def create_access_token(
    *,
    user_id: int,
    username: str,
    role: UserRole,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token with minimal identity claims."""

    expires_at = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "username": username,
        "role": role.value,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)
