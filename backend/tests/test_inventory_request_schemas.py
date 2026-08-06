"""Request contracts for stock-changing sales and deliveries."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.delivery import DeliveryCreate
from app.schemas.sale import SaleCreate


@pytest.mark.parametrize("quantity", [Decimal("0"), Decimal("-1")])
def test_sale_quantity_must_be_positive(quantity: Decimal) -> None:
    with pytest.raises(ValidationError):
        SaleCreate(
            station_id=1,
            tank_id=1,
            pump_id=1,
            fuel_type_id=1,
            sale_timestamp=datetime.now(timezone.utc),
            quantity_liters=quantity,
            unit_price=Decimal("1"),
            duration_seconds=1,
        )


@pytest.mark.parametrize("quantity", [Decimal("0"), Decimal("-1")])
def test_delivery_quantity_must_be_positive(quantity: Decimal) -> None:
    with pytest.raises(ValidationError):
        DeliveryCreate(tank_id=1, quantity_liters=quantity, supplier_name="Supplier")


def test_delivery_timestamp_defaults_to_timezone_aware_utc_now() -> None:
    payload = DeliveryCreate(
        tank_id=1, quantity_liters=Decimal("1"), supplier_name="Supplier"
    )

    assert payload.delivery_timestamp.tzinfo is not None


def test_stock_changing_requests_reject_naive_timestamps() -> None:
    with pytest.raises(ValidationError):
        SaleCreate(
            station_id=1,
            tank_id=1,
            pump_id=1,
            fuel_type_id=1,
            sale_timestamp=datetime(2026, 8, 5, 12, 0),
            quantity_liters=Decimal("1"),
            unit_price=Decimal("1"),
            duration_seconds=1,
        )
    with pytest.raises(ValidationError):
        DeliveryCreate(
            tank_id=1,
            delivery_timestamp=datetime(2026, 8, 5, 12, 0),
            quantity_liters=Decimal("1"),
            supplier_name="Supplier",
        )
