"""Authentication request and response schemas."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.enums import UserRole


class LoginRequest(BaseModel):
    """Credentials used to request an access token."""

    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Username cannot be empty.")
        return value


class TokenResponse(BaseModel):
    """Access token payload returned after successful authentication."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(gt=0)


class OAuth2TokenResponse(BaseModel):
    """OAuth2-compatible token payload returned to Swagger UI."""

    access_token: str
    token_type: str = "bearer"


class CurrentUserResponse(BaseModel):
    """Safe representation of the authenticated user."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str
    role: UserRole
    is_active: bool
