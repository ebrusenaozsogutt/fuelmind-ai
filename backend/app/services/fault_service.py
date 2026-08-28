"""Fault lifecycle, target validation, and explicit alarm linkage."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.exceptions import BusinessRuleError, NotFoundError
from app.models.alarm import Alarm
from app.models.communication_port import CommunicationPort
from app.models.device_controller import DeviceController
from app.models.fault import Fault
from app.models.nozzle import Nozzle
from app.models.pump import Pump
from app.models.station import Station
from app.models.tank import Tank
from app.models.tank_probe import TankProbe
from app.models.user import User
from app.schemas.fault import FaultCreate
from app.services.audit_service import AuditService
from app.utils.datetime_utils import utc_now
from app.utils.enums import AlarmStatus, AuditAction, FaultStatus, FaultTargetType


class FaultService:
    """Keep durable fault records separate from real-time alarm detection."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, fault_id: int) -> Fault:
        fault = self.db.get(Fault, fault_id)
        if fault is None:
            raise NotFoundError("Fault not found.")
        return fault

    def list(
        self,
        *,
        station_id: int | None = None,
        fault_type: object | None = None,
        fault_code: object | None = None,
        status: object | None = None,
        target_type: object | None = None,
        target_id: int | None = None,
        alarm_id: int | None = None,
        detected_from: datetime | None = None,
        detected_to: datetime | None = None,
    ) -> list[Fault]:
        statement = select(Fault).options(selectinload(Fault.resolver_user))
        for column, value in (
            (Fault.station_id, station_id), (Fault.fault_type, fault_type),
            (Fault.fault_code, fault_code), (Fault.status, status),
            (Fault.target_type, target_type), (Fault.target_id, target_id),
            (Fault.alarm_id, alarm_id),
        ):
            if value is not None:
                statement = statement.where(column == value)
        if detected_from is not None:
            statement = statement.where(Fault.detected_at >= detected_from)
        if detected_to is not None:
            statement = statement.where(Fault.detected_at <= detected_to)
        return list(self.db.scalars(statement.order_by(Fault.detected_at.desc(), Fault.id.desc())))

    def create(self, payload: FaultCreate, *, user_id: int | None = None, username: str | None = None) -> Fault:
        station = self.db.get(Station, payload.station_id)
        if station is None:
            raise NotFoundError("Station not found.")
        self._validate_target(payload.station_id, payload.target_type, payload.target_id)
        if payload.alarm_id is not None:
            alarm = self.db.get(Alarm, payload.alarm_id)
            if alarm is None:
                raise NotFoundError("Alarm not found.")
            if alarm.status == AlarmStatus.FALSE_POSITIVE:
                raise BusinessRuleError("Cannot create a fault from a false-positive alarm.")
            if alarm.station_id != payload.station_id:
                raise BusinessRuleError("Fault alarm must belong to the same station.")
            if self.db.scalar(select(Fault.id).where(Fault.alarm_id == alarm.id)) is not None:
                raise BusinessRuleError("This alarm already has a fault record.")
        fault = Fault(**payload.model_dump())
        try:
            self.db.add(fault)
            self.db.flush()
            AuditService(self.db).record(action=AuditAction.CREATE, entity_type="FAULT", entity_id=fault.id, user_id=user_id, username=username, station_id=fault.station_id, new_values={"fault_code": fault.fault_code, "fault_type": fault.fault_type, "status": fault.status, "cause": fault.cause}, description="Fault created")
            self.db.commit()
            self.db.refresh(fault)
            return fault
        except Exception:
            self.db.rollback()
            raise

    def investigate(self, fault_id: int, *, user_id: int | None = None, username: str | None = None) -> Fault:
        fault = self.get(fault_id)
        if fault.status == FaultStatus.RESOLVED:
            raise BusinessRuleError("Resolved faults cannot be investigated.")
        if fault.status != FaultStatus.OPEN:
            raise BusinessRuleError("Only open faults can be investigated.")
        old_status = fault.status
        fault.status = FaultStatus.INVESTIGATING
        AuditService(self.db).record(action=AuditAction.INVESTIGATE, entity_type="FAULT", entity_id=fault.id, user_id=user_id, username=username, station_id=fault.station_id, old_values={"status": old_status}, new_values={"status": fault.status}, description="Fault investigation started")
        return self._commit(fault)

    def resolve(self, fault_id: int, *, user_id: int, resolution_note: str, username: str | None = None) -> Fault:
        fault = self.get(fault_id)
        if fault.status == FaultStatus.RESOLVED:
            raise BusinessRuleError("Fault is already resolved.")
        note = resolution_note.strip()
        if not note:
            raise BusinessRuleError("A resolution note is required.")
        user = self.db.get(User, user_id)
        if user is None or not user.is_active:
            raise BusinessRuleError("Resolver user must be active.")
        old_values = {"status": fault.status, "resolution_note": fault.resolution_note}
        fault.status = FaultStatus.RESOLVED
        fault.resolved_at = utc_now()
        fault.resolved_by = user_id
        fault.resolution_note = note
        AuditService(self.db).record(action=AuditAction.RESOLVE, entity_type="FAULT", entity_id=fault.id, user_id=user_id, username=username, station_id=fault.station_id, old_values=old_values, new_values={"status": fault.status, "resolution_note": fault.resolution_note, "resolved_by": user_id}, description="Fault resolved")
        return self._commit(fault)

    def _commit(self, fault: Fault) -> Fault:
        try:
            self.db.commit()
            self.db.refresh(fault)
            return fault
        except Exception:
            self.db.rollback()
            raise

    def _validate_target(self, station_id: int, target_type: FaultTargetType, target_id: int) -> None:
        target_station_id = self._target_station_id(target_type, target_id)
        if target_station_id is None:
            raise NotFoundError("Fault target not found.")
        if target_station_id != station_id:
            raise BusinessRuleError("Fault target must belong to the fault station.")

    def _target_station_id(self, target_type: FaultTargetType, target_id: int) -> int | None:
        if target_type == FaultTargetType.CONTROLLER:
            target = self.db.get(DeviceController, target_id)
            return target.station_id if target else None
        if target_type == FaultTargetType.PORT:
            return self.db.scalar(select(DeviceController.station_id).join(CommunicationPort).where(CommunicationPort.id == target_id))
        if target_type == FaultTargetType.PUMP:
            target = self.db.get(Pump, target_id)
            return target.station_id if target else None
        if target_type == FaultTargetType.TANK:
            target = self.db.get(Tank, target_id)
            return target.station_id if target else None
        if target_type == FaultTargetType.NOZZLE:
            return self.db.scalar(select(Pump.station_id).join(Nozzle).where(Nozzle.id == target_id))
        if target_type in {FaultTargetType.PROBE, FaultTargetType.SENSOR}:
            return self.db.scalar(select(Tank.station_id).join(TankProbe).where(TankProbe.id == target_id))
        return None
