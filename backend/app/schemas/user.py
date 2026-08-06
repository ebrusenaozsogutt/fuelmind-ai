"""User API schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.enums import UserRole


class UserBase(BaseModel):
    """Fields shared by user input schemas."""

    username: str = Field(min_length=3, max_length=64)
    full_name: str = Field(min_length=1, max_length=150)
    role: UserRole = UserRole.OPERATOR
    is_active: bool = True

    @field_validator("username", "full_name")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be empty.")
        return value


class UserCreate(UserBase):
    """Payload for creating a user; password hashes are never accepted."""

    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    """Payload for partially updating a user."""

    username: str | None = Field(default=None, min_length=3, max_length=64)
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: UserRole | None = None
    is_active: bool | None = None

    @field_validator("username", "full_name")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be empty.")
        return value


class UserRead(BaseModel):
    """Safe user response without password material."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
