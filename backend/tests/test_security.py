"""Password hashing and development seed tests."""

from types import SimpleNamespace

import pytest

from app import seed
from app.exceptions import BusinessRuleError
from app.utils.enums import UserRole
from app.utils.security import hash_password, verify_password


class FakeSession:
    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

    def refresh(self, _: object) -> None:
        pass


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[str, SimpleNamespace] = {}

    def get_by_username(self, username: str) -> SimpleNamespace | None:
        return self.users.get(username)

    def create(self, values: dict[str, object]) -> SimpleNamespace:
        user = SimpleNamespace(id=len(self.users) + 1, **values)
        self.users[user.username] = user
        return user


def test_normal_password_can_be_hashed() -> None:
    password_hash = hash_password("safe-password")
    assert password_hash != "safe-password"


def test_correct_password_is_verified() -> None:
    password_hash = hash_password("safe-password")
    assert verify_password("safe-password", password_hash)


def test_wrong_password_is_rejected() -> None:
    password_hash = hash_password("safe-password")
    assert not verify_password("different-password", password_hash)


def test_password_over_72_utf8_bytes_is_rejected() -> None:
    password = "ş" * 37  # 74 UTF-8 bytes, while still only 37 characters.
    with pytest.raises(BusinessRuleError, match="72 bytes"):
        hash_password(password)


def test_development_demo_seed_hashes_passwords(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeUserRepository()
    monkeypatch.setattr(seed, "UserRepository", lambda _: repository)
    monkeypatch.setattr(seed.settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(seed.settings, "ENABLE_DEMO_USERS", True)
    monkeypatch.setattr(seed.settings, "DEMO_ADMIN_PASSWORD", "demo-admin-password")
    monkeypatch.setattr(
        seed.settings, "DEMO_OPERATOR_PASSWORD", "demo-operator-password"
    )

    created = seed.seed_demo_users(FakeSession())

    assert {user.username for user in created} == {"admin", "operator"}
    assert repository.users["admin"].role == UserRole.ADMIN
    assert repository.users["admin"].password_hash != "demo-admin-password"
    assert verify_password(
        "demo-admin-password", repository.users["admin"].password_hash
    )
