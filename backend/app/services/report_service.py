"""Read-only reports over persisted operational and commercial records."""

from datetime import datetime, time, timezone
from typing import Any

from sqlalchemy import Time, cast, func, select
from sqlalchemy.orm import Session

from app.exceptions import BusinessRuleError
from app.models.alarm import Alarm
from app.models.audit_log import AuditLog
from app.models.commercial import Customer, FuelCard, FuelPrice, Vehicle
from app.models.delivery import Delivery
from app.models.fault import Fault
from app.models.fuel_type import FuelType
from app.models.nozzle import Nozzle
from app.models.operations import Attendant, Shift
from app.models.probe_reading import ProbeReading
from app.models.pump import Pump
from app.models.sale import Sale
from app.models.station import Station
from app.models.tank import Tank
from app.models.tank_probe import TankProbe
from app.models.user import User
from app.schemas.report import ReportFilters
from app.utils.datetime_utils import utc_now
from app.utils.enums import SaleStatus


class ReportService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def sales(self, filters: ReportFilters, skip: int, limit: int) -> list[dict[str, Any]]:
        statement = self._sale_statement(filters).order_by(Sale.sale_timestamp.desc()).offset(skip).limit(limit)
        return [self._sale_row(row) for row in self.db.execute(statement)]

    def end_of_day(self, filters: ReportFilters) -> dict[str, Any]:
        completed = self._sale_statement(filters, completed=True).subquery()
        totals = self.db.execute(select(func.count(), func.coalesce(func.sum(completed.c.quantity_liters), 0), func.coalesce(func.sum(completed.c.total_amount), 0))).one()
        def grouped(column: Any) -> list[dict[str, Any]]:
            rows = self.db.execute(select(column.label("key"), func.count(), func.coalesce(func.sum(completed.c.quantity_liters), 0), func.coalesce(func.sum(completed.c.total_amount), 0)).group_by(column)).all()
            return [{"key": row[0], "transaction_count": row[1], "total_liters": row[2], "total_amount": row[3]} for row in rows]
        return {"transaction_count": totals[0], "total_liters": totals[1], "total_amount": totals[2], "by_fuel_type": grouped(completed.c.fuel_type_name), "by_pump": grouped(completed.c.pump_code), "by_customer": grouped(completed.c.customer_name), "by_payment_type": grouped(completed.c.payment_type)}

    def attendants(self, filters: ReportFilters) -> list[dict[str, Any]]:
        completed = self._sale_statement(filters, completed=True).subquery()
        rows = self.db.execute(select(completed.c.attendant_id, completed.c.attendant_name, completed.c.shift_id, completed.c.shift_name, func.count(), func.coalesce(func.sum(completed.c.quantity_liters), 0), func.coalesce(func.sum(completed.c.total_amount), 0)).group_by(completed.c.attendant_id, completed.c.attendant_name, completed.c.shift_id, completed.c.shift_name)).all()
        return [{"attendant_id": r[0], "attendant_name": r[1], "shift_id": r[2], "shift_name": r[3], "transaction_count": r[4], "total_liters": r[5], "total_amount": r[6]} for r in rows]

    def deliveries(self, filters: ReportFilters, skip: int, limit: int) -> list[dict[str, Any]]:
        self._validate(filters)
        q = select(Delivery, Tank, Station, FuelType).select_from(Delivery).join(Tank, Tank.id == Delivery.tank_id).join(Station, Station.id == Tank.station_id).join(FuelType, FuelType.id == Tank.fuel_type_id)
        q = self._filters(q, Delivery.delivery_timestamp, Tank.station_id, None, None, Tank.fuel_type_id, filters).order_by(Delivery.delivery_timestamp.desc()).offset(skip).limit(limit)
        return [{"id": d.id, "timestamp": d.delivery_timestamp, "station_id": s.id, "station": s.name, "tank_id": t.id, "tank": t.code, "fuel_type": f.name, "level_before": d.level_before, "quantity_liters": d.quantity_liters, "level_after": d.level_after, "supplier": d.supplier_name, "source": "SIMULATION" if d.simulation_run_id else "MANUAL", "status": "COMPLETED"} for d, t, s, f in self.db.execute(q)]

    def tank_measurements(self, filters: ReportFilters, skip: int, limit: int) -> list[dict[str, Any]]:
        self._validate(filters)
        q = select(ProbeReading, TankProbe, Tank, Station).select_from(ProbeReading).join(TankProbe, TankProbe.id == ProbeReading.probe_id).join(Tank, Tank.id == ProbeReading.tank_id).join(Station, Station.id == Tank.station_id)
        q = self._filters(q, ProbeReading.reading_timestamp, Tank.station_id, None, None, Tank.fuel_type_id, filters).order_by(ProbeReading.reading_timestamp.desc()).offset(skip).limit(limit)
        return [{"timestamp": r.reading_timestamp, "station": s.name, "tank": t.code, "probe": p.code, "fuel_height_mm": r.fuel_height_mm, "fuel_volume_liters": r.fuel_volume_liters, "water_height_mm": r.water_height_mm, "temperature_celsius": r.temperature_celsius, "quality_score": r.data_quality_score, "quality_flags": r.quality_flags_json, "source": r.source_type, "probe_status": p.status} for r, p, t, s in self.db.execute(q)]

    def price_changes(self, filters: ReportFilters, skip: int, limit: int) -> list[dict[str, Any]]:
        self._validate(filters)
        q = select(AuditLog, FuelPrice, FuelType, Station).select_from(AuditLog).join(FuelPrice, FuelPrice.id == AuditLog.entity_id).join(FuelType, FuelType.id == FuelPrice.fuel_type_id).join(Station, Station.id == FuelPrice.station_id).where(AuditLog.entity_type == "FUEL_PRICE")
        q = self._filters(q, AuditLog.created_at, Station.id, None, None, FuelType.id, filters).order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
        return [{"price_id": price.id, "timestamp": audit.created_at, "station": station.name, "fuel_type": fuel.name, "old_price": (audit.old_values_json or {}).get("unit_price"), "new_price": (audit.new_values_json or {}).get("unit_price", price.unit_price), "changed_by": audit.username_snapshot} for audit, price, fuel, station in self.db.execute(q)]

    def faults(self, filters: ReportFilters, skip: int, limit: int) -> list[dict[str, Any]]:
        self._validate(filters)
        q = select(Fault, Station, Alarm, User).select_from(Fault).join(Station, Station.id == Fault.station_id).outerjoin(Alarm, Alarm.id == Fault.alarm_id).outerjoin(User, User.id == Fault.resolved_by)
        q = self._filters(q, Fault.detected_at, Fault.station_id, None, None, None, filters).order_by(Fault.detected_at.desc()).offset(skip).limit(limit)
        return [{"id": f.id, "station": s.name, "target_type": f.target_type, "target_id": f.target_id, "fault_type": f.fault_type, "fault_code": f.fault_code, "cause": f.cause, "description": f.description, "started_at": f.started_at, "detected_at": f.detected_at, "resolved_at": f.resolved_at, "duration_seconds": int(((f.resolved_at or utc_now()) - f.started_at).total_seconds()), "status": f.status, "related_alarm_id": f.alarm_id, "resolution_note": f.resolution_note, "resolved_by": u.username if u else None} for f, s, a, u in self.db.execute(q)]

    def customer_sales(self, filters: ReportFilters) -> list[dict[str, Any]]:
        completed = self._sale_statement(filters, completed=True).subquery()
        rows = self.db.execute(select(completed.c.customer_id, completed.c.customer_name, completed.c.vehicle_id, completed.c.plate, completed.c.card_code, func.count(), func.coalesce(func.sum(completed.c.quantity_liters), 0), func.coalesce(func.sum(completed.c.total_amount), 0)).group_by(completed.c.customer_id, completed.c.customer_name, completed.c.vehicle_id, completed.c.plate, completed.c.card_code)).all()
        return [{"customer_id": r[0], "customer": r[1], "vehicle_id": r[2], "plate": r[3], "card": r[4], "transaction_count": r[5], "total_liters": r[6], "total_amount": r[7]} for r in rows]

    def _sale_statement(self, filters: ReportFilters, completed: bool = False):
        self._validate(filters)
        q = select(Sale.id.label("sale_id"), Sale.sale_timestamp, Sale.station_id, Station.name.label("station"), Sale.pump_id, Pump.code.label("pump_code"), Sale.nozzle_id, Nozzle.code.label("nozzle_code"), Sale.attendant_id, Attendant.full_name.label("attendant_name"), Sale.shift_id, Shift.name.label("shift_name"), Sale.fuel_type_id, FuelType.name.label("fuel_type_name"), Sale.quantity_liters, Sale.start_totalizer_liters, Sale.end_totalizer_liters, Sale.unit_price, Sale.total_amount, Sale.customer_id, Customer.name.label("customer_name"), Sale.vehicle_id, Vehicle.plate, FuelCard.card_code, Sale.payment_type, Sale.sale_status).select_from(Sale).join(Station, Station.id == Sale.station_id).join(Pump, Pump.id == Sale.pump_id).outerjoin(Nozzle, Nozzle.id == Sale.nozzle_id).outerjoin(Attendant, Attendant.id == Sale.attendant_id).outerjoin(Shift, Shift.id == Sale.shift_id).join(FuelType, FuelType.id == Sale.fuel_type_id).outerjoin(Customer, Customer.id == Sale.customer_id).outerjoin(Vehicle, Vehicle.id == Sale.vehicle_id).outerjoin(FuelCard, FuelCard.id == Sale.fuel_card_id)
        q = self._filters(q, Sale.sale_timestamp, Sale.station_id, Sale.pump_id, Sale.nozzle_id, Sale.fuel_type_id, filters, sale_filters=True)
        if completed:
            q = q.where(Sale.sale_status == SaleStatus.COMPLETED)
        return q

    def _filters(self, q: Any, timestamp: Any, station: Any, pump: Any, nozzle: Any, fuel: Any, f: ReportFilters, sale_filters: bool = False):
        if f.station_id:
            q = q.where(station == f.station_id)
        if f.pump_id and pump is not None:
            q = q.where(pump == f.pump_id)
        if f.nozzle_id and nozzle is not None:
            q = q.where(nozzle == f.nozzle_id)
        if f.fuel_type_id and fuel is not None:
            q = q.where(fuel == f.fuel_type_id)
        if sale_filters and f.customer_id:
            q = q.where(Sale.customer_id == f.customer_id)
        if sale_filters and f.vehicle_id:
            q = q.where(Sale.vehicle_id == f.vehicle_id)
        if sale_filters and f.plate:
            q = q.where(Vehicle.plate.ilike(f"%{f.plate.strip()}%"))
        if sale_filters and f.attendant_id:
            q = q.where(Sale.attendant_id == f.attendant_id)
        if sale_filters and f.shift_id:
            q = q.where(Sale.shift_id == f.shift_id)
        if f.date_from:
            q = q.where(timestamp >= datetime.combine(f.date_from, f.time_from or time.min, tzinfo=timezone.utc))
        if f.date_to:
            q = q.where(timestamp <= datetime.combine(f.date_to, f.time_to or time.max, tzinfo=timezone.utc))
        elif f.date_from and not f.time_from:
            q = q.where(timestamp <= datetime.combine(f.date_from, time.max, tzinfo=timezone.utc))
        if f.time_from and not f.date_from:
            q = q.where(cast(timestamp, Time) >= f.time_from)
        if f.time_to and not f.date_to:
            q = q.where(cast(timestamp, Time) <= f.time_to)
        return q

    def _validate(self, f: ReportFilters) -> None:
        if f.pump_id and f.station_id and self.db.scalar(select(Pump.station_id).where(Pump.id == f.pump_id)) != f.station_id:
            raise BusinessRuleError("Pump does not belong to station.")
        if f.nozzle_id:
            row = self.db.execute(select(Pump.station_id, Nozzle.pump_id).join(Nozzle).where(Nozzle.id == f.nozzle_id)).one_or_none()
            if row is None or (f.station_id and row[0] != f.station_id) or (f.pump_id and row[1] != f.pump_id):
                raise BusinessRuleError("Nozzle does not match the supplied station or pump.")

    @staticmethod
    def _sale_row(r: Any) -> dict[str, Any]:
        return {"sale_id": r.sale_id, "timestamp": r.sale_timestamp, "station": r.station, "pump": r.pump_code, "nozzle": r.nozzle_code, "attendant": r.attendant_name, "shift": r.shift_name, "fuel_type": r.fuel_type_name, "liters": r.quantity_liters, "start_totalizer": r.start_totalizer_liters, "end_totalizer": r.end_totalizer_liters, "unit_price": r.unit_price, "total_amount": r.total_amount, "customer": r.customer_name, "plate": r.plate, "card": r.card_code, "payment_type": r.payment_type, "sale_status": r.sale_status}
