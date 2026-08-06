"""Authentication API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_active_user
from app.config import settings
from app.database import get_db
from app.exceptions import AuthenticationError
from app.models.user import User
from app.schemas.auth import (
    CurrentUserResponse,
    LoginRequest,
    OAuth2TokenResponse,
    TokenResponse,
)
from app.services.auth_service import AuthService
from app.utils.security import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])
_invalid_credentials = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid username or password.",
    headers={"WWW-Authenticate": "Bearer"},
)


def _authenticate_user(db: Session, username: str, password: str) -> User:
    """Use the shared service and map expected failures to a generic 401."""

    try:
        return AuthService(db).authenticate(username, password)
    except AuthenticationError:
        raise _invalid_credentials from None


def _create_token(user: User) -> str:
    """Issue an access token with the configured lifetime."""

    return create_access_token(user_id=user.id, username=user.username, role=user.role)


@router.post("/login", response_model=TokenResponse)
def login(
    credentials: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """Authenticate a JSON credential payload and issue an access token."""

    user = _authenticate_user(db, credentials.username, credentials.password)
    return TokenResponse(
        access_token=_create_token(user),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/token", response_model=OAuth2TokenResponse)
def issue_oauth2_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)],
) -> OAuth2TokenResponse:
    """OAuth2 form endpoint used by Swagger UI's Authorize dialog."""

    user = _authenticate_user(db, form_data.username, form_data.password)
    return OAuth2TokenResponse(access_token=_create_token(user))


@router.get("/me", response_model=CurrentUserResponse)
def read_current_user(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> CurrentUserResponse:
    """Return safe details of the user represented by a valid bearer token."""

    return CurrentUserResponse.model_validate(current_user)
