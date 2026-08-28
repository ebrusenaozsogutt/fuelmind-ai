"""One-transaction commercial fuel-sale completion workflow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import BusinessRuleError, NotFoundError
from app.models.commercial import (
    Customer,
    Fleet,
    FleetGroup,
    FuelCard,
    FuelCardAllowedFuelType,
    FuelCardAllowedStation,
    Vehicle,
)
from app.models.nozzle import Nozzle
from app.models.pump import Pump
from app.models.tank import Tank
from app.repositories.customer_repository import CustomerRepository
from app.repositories.driver_vehicle_assignment_repository import (
    DriverVehicleAssignmentRepository,
)
from app.repositories.fleet_group_repository import FleetGroupRepository
from app.repositories.fleet_repository import FleetRepository
from app.repositories.fuel_card_repository import FuelCardRepository
from app.repositories.nozzle_repository import NozzleRepository
from app.repositories.sale_repository import SaleRepository
from app.repositories.station_repository import StationRepository
from app.repositories.tank_repository import TankRepository
from app.repositories.vehicle_repository import VehicleRepository
from app.schemas.fuel_card_authorization import FuelCardAuthorizationRequest
from app.schemas.sale import CommercialSaleRequest, CommercialSaleResponse, SaleRead
from app.services.fuel_card_authorization_service import FuelCardAuthorizationService
from app.services.fuel_price_service import FuelPricingService
from app.utils.enums import CardStatus, NozzleStatus, PaymentType, PumpStatus, SaleStatus


QUANTITY_PRECISION = Decimal("0.001")


@dataclass(frozen=True)
class CommercialSaleContext:
    """Trusted commercial and forecourt entities derived from card and nozzle."""

    customer: Customer
    fleet: Fleet
    fleet_group: FleetGroup
    vehicle: Vehicle
    fuel_card: FuelCard
    nozzle: Nozzle
    pump: Pump
    tank: Tank
    driver_id: int | None
    started_at: datetime


@dataclass(frozen=True)
class CommercialSaleSnapshot:
    """Commercial values chosen at simulation sale start and frozen until completion."""

    customer_id: int
    fleet_id: int
    fleet_group_id: int
    vehicle_id: int
    driver_id: int | None
    fuel_card_id: int
    list_unit_price: Decimal
    discount_rate: Decimal
    applied_unit_price: Decimal
    payment_type: PaymentType


@dataclass(frozen=True)
class CommercialSaleSelection:
    """Distinguish no commercial setup from a rejected configured setup."""

    configured: bool
    snapshot: CommercialSaleSnapshot | None = None
    decision_code: str | None = None


class CommercialSaleService:
    """Authorize, price, settle, totalize, and persist one completed sale atomically."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.cards = FuelCardRepository(db)
        self.nozzles = NozzleRepository(db)
        self.tanks = TankRepository(db)
        self.stations = StationRepository(db)
        self.vehicles = VehicleRepository(db)
        self.groups = FleetGroupRepository(db)
        self.fleets = FleetRepository(db)
        self.customers = CustomerRepository(db)
        self.assignments = DriverVehicleAssignmentRepository(db)
        self.sales = SaleRepository(db)

    def complete(self, payload: CommercialSaleRequest) -> CommercialSaleResponse:
        """Run the whole commercial dispense completion in one database transaction."""

        card = self.cards.by_unit_for_update(payload.unit_id)
        if card is None:
            return self._rejected("CARD_NOT_FOUND", "Fuel card not found.")
        nozzle = self.nozzles.get_for_update(payload.nozzle_id)
        if nozzle is None:
            return self._rejected("NOZZLE_NOT_FOUND", "Nozzle not found.")

        try:
            context = self._context(card, nozzle, payload.started_at)
            authorization = FuelCardAuthorizationService(self.db).authorize(
                FuelCardAuthorizationRequest(
                    unit_id=card.unit_id,
                    vehicle_id=context.vehicle.id,
                    station_id=context.pump.station_id,
                    fuel_type_id=nozzle.fuel_type_id,
                    requested_quantity_liters=payload.quantity_liters,
                    requested_at=payload.started_at,
                )
            )
            if not authorization.authorized:
                return self._rejected(
                    authorization.decision_code.value, authorization.message
                )

            pricing = FuelPricingService(self.db).calculate_sale_price(
                customer_id=context.customer.id,
                station_id=context.pump.station_id,
                fuel_type_id=nozzle.fuel_type_id,
                quantity_liters=payload.quantity_liters,
                requested_at=payload.started_at,
            )
            payment_failure = self._payment_failure(card, pricing.total_amount)
            if payment_failure is not None:
                return payment_failure
            if context.tank.current_level_liters < payload.quantity_liters:
                return self._rejected(
                    "TANK_INSUFFICIENT_FUEL",
                    "Tank does not contain enough fuel for this sale.",
                )

            quantity = payload.quantity_liters.quantize(QUANTITY_PRECISION)
            start_totalizer = Decimal(context.nozzle.totalizer_liters).quantize(
                QUANTITY_PRECISION
            )
            end_totalizer = (start_totalizer + quantity).quantize(QUANTITY_PRECISION)
            level_before = Decimal(context.tank.current_level_liters)
            level_after = (level_before - quantity).quantize(QUANTITY_PRECISION)
            self._apply_payment(card, pricing.total_amount)
            context.nozzle.totalizer_liters = end_totalizer
            context.tank.current_level_liters = level_after
            sale = self.sales.create(
                {
                    "station_id": context.pump.station_id,
                    "tank_id": context.tank.id,
                    "pump_id": context.pump.id,
                    "fuel_type_id": context.nozzle.fuel_type_id,
                    "customer_id": context.customer.id,
                    "fleet_id": context.fleet.id,
                    "fleet_group_id": context.fleet_group.id,
                    "vehicle_id": context.vehicle.id,
                    "driver_id": context.driver_id,
                    "fuel_card_id": card.id,
                    "nozzle_id": context.nozzle.id,
                    "sale_timestamp": payload.started_at,
                    "quantity_liters": quantity,
                    "unit_price": pricing.applied_unit_price,
                    "total_amount": pricing.total_amount,
                    "start_totalizer_liters": start_totalizer,
                    "end_totalizer_liters": end_totalizer,
                    "list_unit_price": pricing.list_unit_price,
                    "discount_rate": pricing.discount_rate,
                    "payment_type": card.payment_type,
                    "sale_status": SaleStatus.COMPLETED,
                    "duration_seconds": 0,
                    "level_before": level_before,
                    "level_after": level_after,
                    "is_anomaly": False,
                }
            )
            self.db.commit()
            self.db.refresh(sale)
            return CommercialSaleResponse(
                completed=True,
                decision_code=SaleStatus.COMPLETED.value,
                message="Commercial sale completed.",
                sale=SaleRead.model_validate(sale),
            )
        except NotFoundError as exc:
            self.db.rollback()
            if str(exc) == "Fuel price not configured.":
                return self._rejected("FUEL_PRICE_NOT_CONFIGURED", str(exc))
            raise
        except ValueError as exc:
            self.db.rollback()
            return self._rejected("COMMERCIAL_CONTEXT_INVALID", str(exc))
        except Exception:
            self.db.rollback()
            raise

    def _context(
        self, card: FuelCard, nozzle: Nozzle, started_at: datetime
    ) -> CommercialSaleContext:
        pump = nozzle.pump
        if not nozzle.is_active or nozzle.status != NozzleStatus.AVAILABLE:
            raise ValueError("Nozzle is not available.")
        if not pump.is_active or pump.status not in {PumpStatus.IDLE, PumpStatus.ACTIVE}:
            raise ValueError("Pump is not available.")
        tank = self.tanks.get_for_update(pump.tank_id)
        if tank is None or not tank.is_active:
            raise ValueError("Tank is not available.")
        station = self.stations.get(pump.station_id)
        if station is None or not station.is_active:
            raise ValueError("Station is not available.")
        if tank.station_id != station.id or tank.fuel_type_id != nozzle.fuel_type_id:
            raise ValueError("Nozzle, pump, and tank fuel relationships are inconsistent.")
        vehicle = self.vehicles.get(card.vehicle_id)
        group = self.groups.get(vehicle.fleet_group_id) if vehicle is not None else None
        fleet = self.fleets.get(group.fleet_id) if group is not None else None
        customer = self.customers.get(fleet.customer_id) if fleet is not None else None
        if vehicle is None or group is None or fleet is None or customer is None:
            raise ValueError("Fuel card commercial hierarchy is incomplete.")
        assignment = self.assignments.current_for_vehicle(vehicle.id, started_at.date())
        return CommercialSaleContext(
            customer=customer,
            fleet=fleet,
            fleet_group=group,
            vehicle=vehicle,
            fuel_card=card,
            nozzle=nozzle,
            pump=pump,
            tank=tank,
            driver_id=assignment.driver_id if assignment is not None else None,
            started_at=started_at,
        )

    @staticmethod
    def _payment_failure(
        card: FuelCard, total_amount: Decimal
    ) -> CommercialSaleResponse | None:
        if card.payment_type == PaymentType.PREPAID:
            if card.prepaid_balance < total_amount:
                return CommercialSaleService._rejected(
                    "INSUFFICIENT_PREPAID_BALANCE",
                    "Fuel card prepaid balance is insufficient.",
                )
            return None
        available_credit = card.credit_limit - card.credit_used
        if available_credit < total_amount:
            return CommercialSaleService._rejected(
                "CREDIT_LIMIT_EXCEEDED", "Fuel card credit limit is exceeded."
            )
        return None

    @staticmethod
    def _apply_payment(card: FuelCard, total_amount: Decimal) -> None:
        if card.payment_type == PaymentType.PREPAID:
            card.prepaid_balance -= total_amount
        else:
            card.credit_used += total_amount

    @staticmethod
    def _rejected(decision_code: str, message: str) -> CommercialSaleResponse:
        return CommercialSaleResponse(
            completed=False, decision_code=decision_code, message=message
        )

    def prepare_simulation_sale(
        self,
        *,
        station_id: int,
        fuel_type_id: int,
        quantity_liters: Decimal,
        started_at: datetime,
        random_source: object,
    ) -> CommercialSaleSelection:
        """Select and authorize one card deterministically at simulated sale start."""

        configured = self._has_commercial_configuration(station_id, fuel_type_id)
        if not configured:
            return CommercialSaleSelection(configured=False)
        candidates = list(
            self.db.scalars(
                select(FuelCard)
                .join(Vehicle, FuelCard.vehicle_id == Vehicle.id)
                .join(FleetGroup, Vehicle.fleet_group_id == FleetGroup.id)
                .join(Fleet, FleetGroup.fleet_id == Fleet.id)
                .join(Customer, Fleet.customer_id == Customer.id)
                .join(
                    FuelCardAllowedStation,
                    FuelCardAllowedStation.fuel_card_id == FuelCard.id,
                )
                .join(
                    FuelCardAllowedFuelType,
                    FuelCardAllowedFuelType.fuel_card_id == FuelCard.id,
                )
                .where(
                    FuelCard.is_active.is_(True),
                    FuelCard.status == CardStatus.ACTIVE,
                    Vehicle.is_active.is_(True),
                    FleetGroup.is_active.is_(True),
                    Fleet.is_active.is_(True),
                    Customer.is_active.is_(True),
                    FuelCardAllowedStation.station_id == station_id,
                    FuelCardAllowedFuelType.fuel_type_id == fuel_type_id,
                )
                .order_by(FuelCard.id)
            )
        )
        decision_code = "NO_AUTHORIZED_CARD"
        while candidates:
            card = random_source.choice(candidates)  # type: ignore[attr-defined]
            candidates.remove(card)
            authorization = FuelCardAuthorizationService(self.db).authorize(
                FuelCardAuthorizationRequest(
                    unit_id=card.unit_id,
                    vehicle_id=card.vehicle_id,
                    station_id=station_id,
                    fuel_type_id=fuel_type_id,
                    requested_quantity_liters=quantity_liters,
                    requested_at=started_at,
                )
            )
            if not authorization.authorized:
                decision_code = authorization.decision_code.value
                continue
            vehicle = self.vehicles.get(card.vehicle_id)
            group = self.groups.get(vehicle.fleet_group_id) if vehicle else None
            fleet = self.fleets.get(group.fleet_id) if group else None
            customer = self.customers.get(fleet.customer_id) if fleet else None
            if vehicle is None or group is None or fleet is None or customer is None:
                continue
            try:
                pricing = FuelPricingService(self.db).calculate_sale_price(
                    customer_id=customer.id,
                    station_id=station_id,
                    fuel_type_id=fuel_type_id,
                    quantity_liters=quantity_liters,
                    requested_at=started_at,
                )
            except NotFoundError:
                decision_code = "FUEL_PRICE_NOT_CONFIGURED"
                continue
            # Authorization validates operational/card rules, while monetary
            # capacity is priced here.  Reject this candidate before an
            # in-memory simulation sale starts so another eligible card can
            # be selected instead of failing at settlement time.
            payment_failure = self._payment_failure(card, pricing.total_amount)
            if payment_failure is not None:
                decision_code = payment_failure.decision_code
                continue
            assignment = self.assignments.current_for_vehicle(vehicle.id, started_at.date())
            return CommercialSaleSelection(
                configured=True,
                snapshot=CommercialSaleSnapshot(
                    customer_id=customer.id,
                    fleet_id=fleet.id,
                    fleet_group_id=group.id,
                    vehicle_id=vehicle.id,
                    driver_id=assignment.driver_id if assignment else None,
                    fuel_card_id=card.id,
                    list_unit_price=pricing.list_unit_price,
                    discount_rate=pricing.discount_rate,
                    applied_unit_price=pricing.applied_unit_price,
                    payment_type=card.payment_type,
                ),
            )
        return CommercialSaleSelection(configured=True, decision_code=decision_code)

    def finalize_simulation_payment(
        self, snapshot: CommercialSaleSnapshot, quantity_liters: Decimal
    ) -> Decimal:
        """Re-check and mutate financial state inside tick persistence's transaction."""

        card = self.db.scalar(
            select(FuelCard).where(FuelCard.id == snapshot.fuel_card_id).with_for_update()
        )
        if card is None:
            raise BusinessRuleError("Fuel card disappeared before sale completion.")
        total_amount = (snapshot.applied_unit_price * quantity_liters).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        failure = self._payment_failure(card, total_amount)
        if failure is not None:
            raise BusinessRuleError(failure.message)
        self._apply_payment(card, total_amount)
        return total_amount

    def _has_commercial_configuration(self, station_id: int, fuel_type_id: int) -> bool:
        """Bounded check that also treats blocked configured cards as commercial mode."""

        statement = (
            select(FuelCard.id)
            .join(Vehicle, FuelCard.vehicle_id == Vehicle.id)
            .join(FleetGroup, Vehicle.fleet_group_id == FleetGroup.id)
            .join(Fleet, FleetGroup.fleet_id == Fleet.id)
            .join(Customer, Fleet.customer_id == Customer.id)
            .join(
                FuelCardAllowedStation,
                FuelCardAllowedStation.fuel_card_id == FuelCard.id,
            )
            .join(
                FuelCardAllowedFuelType,
                FuelCardAllowedFuelType.fuel_card_id == FuelCard.id,
            )
            .where(
                FuelCardAllowedStation.station_id == station_id,
                FuelCardAllowedFuelType.fuel_type_id == fuel_type_id,
            )
            .limit(1)
        )
        return self.db.scalar(statement) is not None
