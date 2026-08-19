"""Business rules for station fuel-price history and price previews."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.exceptions import BusinessRuleError, NotFoundError
from app.models.commercial import FuelPrice
from app.repositories.customer_repository import CustomerRepository
from app.repositories.fuel_price_repository import FuelPriceRepository
from app.repositories.fuel_type_repository import FuelTypeRepository
from app.repositories.station_repository import StationRepository
from app.schemas.fuel_price import (
    FuelPriceCreate,
    FuelPriceUpdate,
    SalePriceCalculationResult,
)
from app.services.audit_service import AuditService
from app.utils.datetime_utils import utc_now
from app.utils.enums import AuditAction


PRICE_PRECISION = Decimal("0.0001")
MONEY_PRECISION = Decimal("0.01")


def _as_utc(value: datetime) -> datetime:
    """Normalize database and request timestamps for safe interval comparisons."""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class FuelPriceService:
    """Manage immutable price history while protecting active intervals."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = FuelPriceRepository(db)
        self.stations = StationRepository(db)
        self.fuel_types = FuelTypeRepository(db)

    def get(self, fuel_price_id: int) -> FuelPrice:
        entity = self.repository.get(fuel_price_id)
        if entity is None:
            raise NotFoundError("Fuel price not found.")
        return entity

    def list(
        self,
        *,
        station_id: int | None = None,
        fuel_type_id: int | None = None,
        is_active: bool | None = None,
    ) -> list[FuelPrice]:
        return self.repository.list(
            station_id=station_id,
            fuel_type_id=fuel_type_id,
            is_active=is_active,
        )

    def history(self, station_id: int, fuel_type_id: int) -> list[FuelPrice]:
        self._validate_station_and_fuel(station_id, fuel_type_id)
        return self.repository.list_history(station_id, fuel_type_id)

    def current(
        self, station_id: int, fuel_type_id: int, requested_at: datetime
    ) -> FuelPrice:
        self._validate_station_and_fuel(station_id, fuel_type_id)
        entity = self.repository.get_active_price(
            station_id, fuel_type_id, _as_utc(requested_at)
        )
        if entity is None:
            raise NotFoundError("Fuel price not configured.")
        return entity

    def set_price(
        self,
        payload: FuelPriceCreate,
        *,
        created_by: int,
        username: str | None = None,
    ) -> FuelPrice:
        values = payload.model_dump()
        values["effective_from"] = _as_utc(values["effective_from"])
        if values["effective_until"] is not None:
            values["effective_until"] = _as_utc(values["effective_until"])
        self._validate_period(values["effective_from"], values["effective_until"])
        self._validate_station_and_fuel(payload.station_id, payload.fuel_type_id)

        def operation() -> FuelPrice:
            self._close_preceding_open_price(values)
            self._validate_no_overlap(
                station_id=payload.station_id,
                fuel_type_id=payload.fuel_type_id,
                effective_from=values["effective_from"],
                effective_until=values["effective_until"],
            )
            values["created_by"] = created_by
            entity = self.repository.create(values)
            self.db.flush()
            AuditService(self.db).record(action=AuditAction.CREATE, entity_type="FUEL_PRICE", entity_id=entity.id, user_id=created_by, username=username, station_id=entity.station_id, new_values={"unit_price": entity.unit_price, "effective_from": entity.effective_from}, description="Fuel price created")
            return entity

        return self._commit(operation)

    def update(self, fuel_price_id: int, payload: FuelPriceUpdate, *, user_id: int | None = None, username: str | None = None) -> FuelPrice:
        entity = self.get(fuel_price_id)
        values = payload.model_dump(exclude_unset=True)
        if not values:
            return entity

        protected_fields = {
            "station_id",
            "fuel_type_id",
            "unit_price",
            "effective_from",
            "effective_until",
        }
        if _as_utc(entity.effective_from) <= utc_now() and protected_fields.intersection(
            values
        ):
            raise BusinessRuleError(
                "Started fuel price history cannot be rewritten; create a new price."
            )

        station_id = values.get("station_id", entity.station_id)
        fuel_type_id = values.get("fuel_type_id", entity.fuel_type_id)
        effective_from = _as_utc(values.get("effective_from", entity.effective_from))
        effective_until_value = values.get("effective_until", entity.effective_until)
        effective_until = (
            _as_utc(effective_until_value) if effective_until_value is not None else None
        )
        if "effective_from" in values:
            values["effective_from"] = effective_from
        if "effective_until" in values:
            values["effective_until"] = effective_until
        self._validate_period(effective_from, effective_until)
        self._validate_station_and_fuel(station_id, fuel_type_id)

        def operation() -> FuelPrice:
            if values.get("is_active", entity.is_active):
                self._validate_no_overlap(
                    station_id=station_id,
                    fuel_type_id=fuel_type_id,
                    effective_from=effective_from,
                    effective_until=effective_until,
                    exclude_id=entity.id,
                )
            old_values = {key: getattr(entity, key) for key in values}
            updated = self.repository.update(entity, values)
            AuditService(self.db).record(action=AuditAction.UPDATE, entity_type="FUEL_PRICE", entity_id=entity.id, user_id=user_id, username=username, station_id=entity.station_id, old_values=old_values, new_values={key: getattr(updated, key) for key in values}, description="Fuel price changed")
            return updated

        return self._commit(operation)

    def deactivate(self, fuel_price_id: int) -> FuelPrice:
        return self._commit(lambda: self.repository.deactivate(self.get(fuel_price_id)))

    def _close_preceding_open_price(self, values: dict[str, object]) -> None:
        """Close the current open price when a new open price supersedes it."""

        if not values["is_active"] or values["effective_until"] is not None:
            return
        effective_from = values["effective_from"]
        assert isinstance(effective_from, datetime)
        candidates = self.repository.list_active_for_pair(
            int(values["station_id"]), int(values["fuel_type_id"])
        )
        for candidate in candidates:
            if (
                candidate.effective_until is None
                and _as_utc(candidate.effective_from) < effective_from
            ):
                self.repository.update(candidate, {"effective_until": effective_from})

    def _validate_no_overlap(
        self,
        *,
        station_id: int,
        fuel_type_id: int,
        effective_from: datetime,
        effective_until: datetime | None,
        exclude_id: int | None = None,
    ) -> None:
        for candidate in self.repository.list_active_for_pair(station_id, fuel_type_id):
            if candidate.id == exclude_id:
                continue
            candidate_from = _as_utc(candidate.effective_from)
            candidate_until = (
                _as_utc(candidate.effective_until)
                if candidate.effective_until is not None
                else None
            )
            starts_before_candidate_ends = (
                candidate_until is None or effective_from < candidate_until
            )
            candidate_starts_before_end = (
                effective_until is None or candidate_from < effective_until
            )
            if starts_before_candidate_ends and candidate_starts_before_end:
                raise BusinessRuleError("Fuel price interval overlaps existing price.")

    @staticmethod
    def _validate_period(
        effective_from: datetime, effective_until: datetime | None
    ) -> None:
        if effective_until is not None and effective_until < effective_from:
            raise BusinessRuleError("Invalid price period.")

    def _validate_station_and_fuel(self, station_id: int, fuel_type_id: int) -> None:
        if self.stations.get(station_id) is None:
            raise NotFoundError("Station not found.")
        if self.fuel_types.get(fuel_type_id) is None:
            raise NotFoundError("Fuel type not found.")

    def _commit(self, operation: object) -> FuelPrice:
        try:
            entity = operation()  # type: ignore[operator]
            self.db.commit()
            self.db.refresh(entity)
            return entity
        except Exception:
            self.db.rollback()
            raise


class FuelPricingService:
    """Resolve a customer-specific sale-price snapshot without writing a Sale."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.customers = CustomerRepository(db)
        self.prices = FuelPriceService(db)

    def calculate_sale_price(
        self,
        *,
        customer_id: int,
        station_id: int,
        fuel_type_id: int,
        quantity_liters: Decimal,
        requested_at: datetime | None,
    ) -> SalePriceCalculationResult:
        customer = self.customers.get(customer_id)
        if customer is None:
            raise NotFoundError("Customer not found.")
        if not customer.is_active:
            raise BusinessRuleError("Customer inactive.")

        calculated_at = _as_utc(requested_at) if requested_at is not None else utc_now()
        price = self.prices.current(station_id, fuel_type_id, calculated_at)
        list_unit_price = Decimal(price.unit_price).quantize(
            PRICE_PRECISION, rounding=ROUND_HALF_UP
        )
        discount_rate = Decimal(customer.discount_rate)
        if discount_rate < 0 or discount_rate > 100:
            raise BusinessRuleError("Customer discount rate is invalid.")
        discount_amount = (list_unit_price * discount_rate / Decimal("100")).quantize(
            PRICE_PRECISION, rounding=ROUND_HALF_UP
        )
        applied_unit_price = (list_unit_price - discount_amount).quantize(
            PRICE_PRECISION, rounding=ROUND_HALF_UP
        )
        total_amount = (applied_unit_price * quantity_liters).quantize(
            MONEY_PRECISION, rounding=ROUND_HALF_UP
        )
        return SalePriceCalculationResult(
            customer_id=customer_id,
            station_id=station_id,
            fuel_type_id=fuel_type_id,
            quantity_liters=quantity_liters,
            fuel_price_id=price.id,
            list_unit_price=list_unit_price,
            discount_rate=discount_rate,
            discount_amount_per_liter=discount_amount,
            applied_unit_price=applied_unit_price,
            total_amount=total_amount,
            price_effective_from=price.effective_from,
            price_effective_until=price.effective_until,
            calculated_at=calculated_at,
        )
