"""Management API service-rule tests for the Stage 2.7 resources."""

from types import SimpleNamespace

import pytest

from app.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.schemas.fuel_type import FuelTypeCreate
from app.schemas.user import UserUpdate
from app.services.fuel_type_service import FuelTypeService
from app.services.tank_service import TankService
from app.services.user_service import UserService


class FakeSession:
    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

    def refresh(self, _: object) -> None:
        pass


def test_inactive_fuel_type_cannot_be_assigned_to_tank() -> None:
    service = TankService(FakeSession())
    service.station_repository = SimpleNamespace(get=lambda _: object())
    service.fuel_type_repository = SimpleNamespace(
        get=lambda _: SimpleNamespace(is_active=False)
    )

    with pytest.raises(BusinessRuleError, match="must be active"):
        service._validate_references(1, 1)


def test_user_cannot_deactivate_own_account_through_update_or_delete() -> None:
    user = SimpleNamespace(id=1, is_active=True)
    service = UserService(FakeSession())
    service.repository = SimpleNamespace(get=lambda _: user)

    with pytest.raises(BusinessRuleError, match="own account"):
        service.update(1, UserUpdate(is_active=False), actor_id=1)
    with pytest.raises(BusinessRuleError, match="own account"):
        service.deactivate(1, actor_id=1)


def test_fuel_type_duplicate_code_is_rejected() -> None:
    service = FuelTypeService(FakeSession())
    service.repository = SimpleNamespace(
        get_by_code=lambda _: object(), get_by_name=lambda _: None
    )

    with pytest.raises(ConflictError):
        service.create(FuelTypeCreate(name="Diesel", code="DSL"))


def test_management_services_return_not_found_for_unknown_ids() -> None:
    service = UserService(FakeSession())
    service.repository = SimpleNamespace(get=lambda _: None)

    with pytest.raises(NotFoundError):
        service.get(999)
