"""Authentication router tests using an in-memory repository double."""

from dataclasses import dataclass
from datetime import timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from jose import jwt

from app.api import dependencies as auth_dependencies
from app.api.dependencies import require_admin
from app.config import settings
from app.database import get_db
from app.main import app
from app.services import auth_service
from app.utils.enums import UserRole
from app.utils.security import JWT_ALGORITHM, create_access_token, hash_password


@dataclass
class FakeUser:
    id: int
    username: str
    password_hash: str
    full_name: str
    role: UserRole
    is_active: bool = True


class FakeUserRepository:
    def __init__(self, users: list[FakeUser]) -> None:
        self.users = users

    def get_by_username(self, username: str) -> FakeUser | None:
        return next((user for user in self.users if user.username == username), None)

    def get(self, user_id: int) -> FakeUser | None:
        return next((user for user in self.users if user.id == user_id), None)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, FakeUserRepository]:
    users = [
        FakeUser(
            1, "admin", hash_password("correct-password"), "Admin", UserRole.ADMIN
        ),
        FakeUser(
            2,
            "inactive",
            hash_password("correct-password"),
            "Inactive",
            UserRole.OPERATOR,
            False,
        ),
    ]
    repository = FakeUserRepository(users)
    monkeypatch.setattr(auth_service, "UserRepository", lambda _: repository)
    monkeypatch.setattr(auth_dependencies, "UserRepository", lambda _: repository)
    app.dependency_overrides[get_db] = lambda: object()
    with TestClient(app) as test_client:
        yield test_client, repository
    app.dependency_overrides.clear()


def test_json_login_success(client: tuple[TestClient, FakeUserRepository]) -> None:
    response = client[0].post(
        "/api/auth/login", json={"username": "admin", "password": "correct-password"}
    )
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"


def test_json_login_normalizes_username_and_includes_required_claims(
    client: tuple[TestClient, FakeUserRepository],
) -> None:
    response = client[0].post(
        "/api/auth/login",
        json={"username": " admin ", "password": "correct-password"},
    )

    assert response.status_code == 200
    payload = jwt.decode(
        response.json()["access_token"],
        settings.SECRET_KEY,
        algorithms=[JWT_ALGORITHM],
    )
    assert payload["sub"] == "1"
    assert payload["username"] == "admin"
    assert payload["role"] == UserRole.ADMIN.value
    assert "exp" in payload


def test_swagger_form_login_success(
    client: tuple[TestClient, FakeUserRepository],
) -> None:
    response = client[0].post(
        "/api/auth/token",
        data={"username": "admin", "password": "correct-password"},
    )
    assert response.status_code == 200
    assert set(response.json()) == {"access_token", "token_type"}


def test_wrong_password(client: tuple[TestClient, FakeUserRepository]) -> None:
    response = client[0].post(
        "/api/auth/token",
        data={"username": "admin", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid username or password."


def test_unknown_user(client: tuple[TestClient, FakeUserRepository]) -> None:
    response = client[0].post(
        "/api/auth/login", json={"username": "missing", "password": "correct-password"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid username or password."


def test_inactive_user_cannot_login(
    client: tuple[TestClient, FakeUserRepository],
) -> None:
    response = client[0].post(
        "/api/auth/token",
        data={"username": "inactive", "password": "correct-password"},
    )
    assert response.status_code == 401


def test_me_without_token(client: tuple[TestClient, FakeUserRepository]) -> None:
    assert client[0].get("/api/auth/me").status_code == 401


def test_me_with_invalid_token(client: tuple[TestClient, FakeUserRepository]) -> None:
    assert (
        client[0]
        .get("/api/auth/me", headers={"Authorization": "Bearer invalid"})
        .status_code
        == 401
    )


def test_me_with_expired_token_is_rejected(
    client: tuple[TestClient, FakeUserRepository],
) -> None:
    token = create_access_token(
        user_id=1,
        username="admin",
        role=UserRole.ADMIN,
        expires_delta=timedelta(seconds=-1),
    )

    response = client[0].get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


def test_me_with_token_from_json_login(
    client: tuple[TestClient, FakeUserRepository],
) -> None:
    login_response = client[0].post(
        "/api/auth/login",
        json={"username": "admin", "password": "correct-password"},
    )
    token = login_response.json()["access_token"]
    response = client[0].get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["username"] == "admin"
    assert "password_hash" not in response.json()


def test_operator_is_rejected_by_require_admin() -> None:
    operator = FakeUser(
        3,
        "operator",
        hash_password("correct-password"),
        "Operator",
        UserRole.OPERATOR,
    )

    with pytest.raises(HTTPException) as exc_info:
        require_admin(operator)

    assert exc_info.value.status_code == 403


def test_operator_cannot_access_user_management_endpoint(
    client: tuple[TestClient, FakeUserRepository],
) -> None:
    operator = FakeUser(
        3,
        "operator",
        hash_password("correct-password"),
        "Operator",
        UserRole.OPERATOR,
    )
    client[1].users.append(operator)
    token = create_access_token(
        user_id=operator.id,
        username=operator.username,
        role=operator.role,
    )

    response = client[0].get(
        "/api/users", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403
