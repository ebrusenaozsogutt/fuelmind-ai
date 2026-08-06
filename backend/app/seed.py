"""Development-only demo user seed command."""

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.exceptions import BusinessRuleError
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.utils.enums import UserRole
from app.utils.security import hash_password


def seed_demo_users(db: Session) -> list[User]:
    """Create demo users only when explicitly enabled in development."""

    if settings.ENVIRONMENT.lower() != "development" or not settings.ENABLE_DEMO_USERS:
        raise BusinessRuleError("Demo user seeding is only enabled in development.")
    if not settings.DEMO_ADMIN_PASSWORD or not settings.DEMO_OPERATOR_PASSWORD:
        raise BusinessRuleError("Set both demo passwords before running the seed.")

    repository = UserRepository(db)
    created: list[User] = []
    demo_users = (
        ("admin", "Development Admin", UserRole.ADMIN, settings.DEMO_ADMIN_PASSWORD),
        (
            "operator",
            "Development Operator",
            UserRole.OPERATOR,
            settings.DEMO_OPERATOR_PASSWORD,
        ),
    )
    try:
        for username, full_name, role, password in demo_users:
            if repository.get_by_username(username) is None:
                created.append(
                    repository.create(
                        {
                            "username": username,
                            "full_name": full_name,
                            "role": role,
                            "is_active": True,
                            "password_hash": hash_password(password),
                        }
                    )
                )
        db.commit()
        for user in created:
            db.refresh(user)
        return created
    except Exception:
        db.rollback()
        raise


def main() -> None:
    """Run the explicit development seed command."""

    with SessionLocal() as db:
        seed_demo_users(db)


if __name__ == "__main__":
    main()
