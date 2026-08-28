"""Atomic persistence of completed in-memory simulation ticks."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.exceptions import BusinessRuleError
from app.models.delivery import Delivery
from app.models.nozzle import Nozzle
from app.models.probe_reading import ProbeReading
from app.models.sale import Sale
from app.models.sensor_reading import SensorReading
from app.models.simulation_event import SimulationEvent
from app.models.simulation_run import SimulationRun
from app.repositories.simulation_run_repository import SimulationRunRepository
from app.repositories.tank_repository import TankRepository
from app.repositories.sensor_reading_repository import SensorReadingRepository
from app.simulation.state import ActiveSaleState
from app.simulation.tick_result import SimulationTickEvent, SimulationTickResult
from app.utils.enums import SourceType
from app.services.data_quality_service import DataQualityService
from app.services.alarm_engine import AlarmEngine
from app.services.live_anomaly_service import LiveAnomalyService
from app.repositories.alarm_repository import AlarmRepository
from app.utils.enums import AnomalyType
from app.services.commercial_sale_service import CommercialSaleService
from app.services.field_fault_scenario_service import FieldFaultScenarioService


def _decimal(value: float) -> Decimal:
    """Convert generator floats through text to retain their intended decimal value."""

    return Decimal(str(value))


_SALE_QUANTITY_PRECISION = Decimal("0.001")
_MONEY_PRECISION = Decimal("0.01")


def _sale_quantity(value: float) -> Decimal:
    """Use the persisted sale precision for quantities, totals, and totalizers."""

    return _decimal(value).quantize(_SALE_QUANTITY_PRECISION, rounding=ROUND_HALF_UP)


class TickPersistence:
    """Write every durable consequence of one tick in one database transaction."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._runs = SimulationRunRepository(db)
        self._tanks = TankRepository(db)
        self._quality = DataQualityService()
        self._readings = SensorReadingRepository(db)
        self._alarms = AlarmEngine(AlarmRepository(db))
        self._field_faults = FieldFaultScenarioService(db)
        self._alarms_available = (
            inspect(db.get_bind()).has_table("alarms") if hasattr(db, "get_bind") else False
        )
        self._models_available = (
            inspect(db.get_bind()).has_table("model_versions") if hasattr(db, "get_bind") else False
        )

    def persist(self, run_id: int, result: SimulationTickResult) -> bool:
        """Persist one tick and commit it, returning false for an already persisted tick.

        The run row is locked before testing its sequence so retrying a committed tick
        is harmless. Any exception rolls back every write made for this tick and is
        intentionally re-raised to the caller.
        """

        try:
            run = self._runs.get_for_update(run_id)
            if run is None:
                raise ValueError(f"Simulation run {run_id} was not found.")
            if run.station_id != result.station_id:
                raise ValueError("Tick station does not match the simulation run.")
            if result.sequence_number <= run.sequence_number:
                self.db.rollback()
                return False

            readings = self._sensor_readings(run, result)
            probe_readings = self._probe_readings(run, result, readings)
            sales = self._sales(run, result)
            deliveries = self._deliveries(run, result)
            events = self._events(run, result)
            self.db.add_all(readings)
            self.db.add_all(probe_readings)
            self.db.add_all(sales)
            self.db.add_all(deliveries)
            self.db.add_all(events)
            result.created_alarms = self._evaluate_alarms(run, result, readings)
            if result.active_scenarios:
                result.created_alarms += self._field_faults.apply(
                    result.active_scenarios, result.simulation_time
                )
            else:
                self._field_faults.apply([], result.simulation_time)
            self._update_nozzle_totalizers(result.completed_sales)
            self._update_tank_levels(result)
            run.current_simulation_time = result.simulation_time
            run.sequence_number = result.sequence_number
            run.generated_sensor_count += len(readings)
            run.generated_sale_count += len(sales)
            run.generated_delivery_count += len(deliveries)
            self.db.flush()
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return True

    def persist_batch(self, run_id: int, results: list[SimulationTickResult]) -> bool:
        """Persist ordered ticks atomically, committing only their final run state."""

        if not results:
            return True
        try:
            run = self._runs.get_for_update(run_id)
            if run is None:
                raise ValueError(f"Simulation run {run_id} was not found.")
            if any(item.station_id != run.station_id for item in results):
                raise ValueError("Tick station does not match the simulation run.")
            sequences = [item.sequence_number for item in results]
            if sequences != sorted(sequences) or len(set(sequences)) != len(sequences):
                raise ValueError("Batch tick sequences must be strictly increasing.")
            if results[0].sequence_number <= run.sequence_number:
                self.db.rollback()
                return False
            readings_by_result = [
                (result, self._sensor_readings(run, result)) for result in results
            ]
            readings = [reading for _, group in readings_by_result for reading in group]
            probe_readings = [
                reading
                for result, group in readings_by_result
                for reading in self._probe_readings(run, result, group)
            ]
            batch_totalizers: dict[int, Decimal] = {}
            sales = [
                sale
                for result in results
                for sale in self._sales(run, result, totalizers=batch_totalizers)
            ]
            deliveries = [
                delivery for result in results for delivery in self._deliveries(run, result)
            ]
            events = [event for result in results for event in self._events(run, result)]
            self.db.add_all(readings)
            self.db.add_all(probe_readings)
            self.db.add_all(sales)
            self.db.add_all(deliveries)
            self.db.add_all(events)
            for item, group in readings_by_result:
                item.created_alarms = self._evaluate_alarms(run, item, group)
            self._update_nozzle_totalizers(
                [sale for result in results for sale in result.completed_sales]
            )
            last_tank_states = {
                tank.tank_id: tank
                for result in results
                for tank in result.tank_results
            }
            self._update_tank_states(run.station_id, list(last_tank_states.values()))
            last = results[-1]
            run.current_simulation_time = last.simulation_time
            run.sequence_number = last.sequence_number
            run.generated_sensor_count += len(readings)
            run.generated_sale_count += len(sales)
            run.generated_delivery_count += len(deliveries)
            self.db.flush()
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return True

    def _sensor_readings(
        self, run: SimulationRun, result: SimulationTickResult
    ) -> list[SensorReading]:
        readings: list[SensorReading] = []
        for tank in result.tank_results:
            readings.append(
                SensorReading(
                    station_id=result.station_id,
                    tank_id=tank.tank_id,
                    simulation_run_id=run.id,
                    sequence_number=result.sequence_number,
                    reading_timestamp=result.simulation_time,
                    tank_level=_decimal(tank.measured_level_liters),
                    true_tank_level=_decimal(tank.true_level_liters),
                    temperature=_decimal(tank.temperature),
                    water_level=_decimal(tank.water_level),
                    error_count=0,
                    data_quality_score=Decimal("100"), quality_flags_json=[],
                    is_anomaly=False,
                    source_type=SourceType.SIMULATION,
                )
            )
        for pump in result.pump_results:
            readings.append(
                SensorReading(
                    station_id=result.station_id,
                    tank_id=pump.tank_id,
                    pump_id=pump.pump_id,
                    simulation_run_id=run.id,
                    sequence_number=result.sequence_number,
                    reading_timestamp=result.simulation_time,
                    flow_rate=_decimal(pump.flow_rate),
                    pressure=_decimal(pump.pressure),
                    motor_current=_decimal(pump.motor_current),
                    pump_temperature=_decimal(pump.temperature),
                    error_count=pump.error_count,
                    working_duration=_decimal(pump.total_working_hours),
                    data_quality_score=Decimal("100"), quality_flags_json=[],
                    is_anomaly=False,
                    source_type=SourceType.SIMULATION,
                )
            )
        sale_change = {item.pump_id: item.dispensed_quantity_liters for item in result.sale_results}
        for reading in readings:
            capacity = next((tank.capacity_liters for tank in result.tank_results if tank.tank_id == reading.tank_id), None)
            previous = self._readings.latest_for_target(tank_id=reading.tank_id, pump_id=reading.pump_id) if hasattr(self.db, "scalar") else None
            expected = sum(amount for pump_id, amount in sale_change.items() if result.pump_results and next((pump.tank_id for pump in result.pump_results if pump.pump_id == pump_id), None) == reading.tank_id)
            quality = self._quality.assess(reading, previous=previous, capacity_liters=capacity, expected_sale_change=expected)
            reading.data_quality_score, reading.quality_flags_json = quality.score, quality.flags
        return readings

    @staticmethod
    def _probe_readings(
        run: SimulationRun,
        result: SimulationTickResult,
        sensor_readings: list[SensorReading],
    ) -> list[ProbeReading]:
        """Persist the same post-scenario tank measurement seen by each probe."""

        tank_readings = {
            reading.tank_id: reading
            for reading in sensor_readings
            if reading.pump_id is None and reading.tank_id is not None
        }
        readings: list[ProbeReading] = []
        enriched_observations = []
        for observation in result.probe_observations:
            source = tank_readings.get(observation.tank_id)
            if source is None:
                raise ValueError(
                    f"Probe tank {observation.tank_id} has no sensor reading."
                )
            readings.append(
                ProbeReading(
                    probe_id=observation.probe_id,
                    tank_id=observation.tank_id,
                    simulation_run_id=run.id,
                    sequence_number=result.sequence_number,
                    reading_timestamp=result.simulation_time,
                    fuel_height_mm=_decimal(observation.fuel_height_mm),
                    fuel_volume_liters=_decimal(observation.fuel_volume_liters),
                    water_height_mm=_decimal(observation.water_height_mm),
                    water_volume_liters=_decimal(observation.water_volume_liters),
                    temperature_celsius=_decimal(observation.temperature_celsius),
                    data_quality_score=source.data_quality_score,
                    quality_flags_json=list(source.quality_flags_json),
                    source_type=SourceType.SIMULATION,
                )
            )
            enriched_observations.append(
                replace(
                    observation,
                    data_quality_score=float(source.data_quality_score),
                    quality_flags=tuple(source.quality_flags_json),
                )
            )
        result.probe_observations = enriched_observations
        return readings

    def _sales(
        self,
        run: SimulationRun,
        result: SimulationTickResult,
        *,
        totalizers: dict[int, Decimal] | None = None,
    ) -> list[Sale]:
        final_levels = {item.tank_id: item.true_level_liters for item in result.tank_results}
        delivery_levels = {
            item.tank_id: item.level_before_liters for item in result.deliveries
        }
        totalizers = totalizers if totalizers is not None else {}
        sales: list[Sale] = []
        for completed in result.completed_sales:
            quantity = _sale_quantity(completed.dispensed_quantity_liters)
            if quantity <= 0:
                raise ValueError(
                    "Completed simulation sales must have a positive dispensed quantity."
                )
            start_totalizer = None
            end_totalizer = None
            if completed.nozzle_id is not None:
                nozzle_id = completed.nozzle_id
                if nozzle_id not in totalizers:
                    nozzle = self.db.scalar(
                        select(Nozzle).where(Nozzle.id == nozzle_id).with_for_update()
                    )
                    if nozzle is None:
                        raise ValueError(f"Nozzle {nozzle_id} was not found.")
                    totalizers[nozzle_id] = Decimal(nozzle.totalizer_liters)
                start_totalizer = totalizers[nozzle_id]
                end_totalizer = start_totalizer + quantity
                totalizers[nozzle_id] = end_totalizer
            try:
                sales.append(
                    self._sale(
                        run,
                        completed,
                        final_levels,
                        delivery_levels,
                        start_totalizer=start_totalizer,
                        end_totalizer=end_totalizer,
                    )
                )
            except BusinessRuleError as exc:
                # A card may have been selected by another concurrent sale
                # between simulation-sale start and settlement.  That is a
                # normal business rejection, not a runner failure.  Preserve
                # the tick and its physical observations, but never persist a
                # successful Sale or charge the rejected card.
                result.events.append(
                    SimulationTickEvent(
                        "SALE_PAYMENT_REJECTED",
                        result.station_id,
                        result.simulation_time,
                        "PUMP",
                        completed.pump_id,
                        {"sale_id": completed.sale_id, "reason": str(exc)},
                    )
                )
                continue
        return sales

    def _sale(
        self,
        run: SimulationRun,
        completed: ActiveSaleState,
        final_levels: dict[int, float],
        delivery_levels: dict[int, float],
        *,
        start_totalizer: Decimal | None,
        end_totalizer: Decimal | None,
    ) -> Sale:
        level_after = delivery_levels.get(
            completed.tank_id, final_levels[completed.tank_id]
        )
        quantity = _sale_quantity(completed.dispensed_quantity_liters)
        commercial_values: dict[str, object] = {}
        unit_price = _decimal(completed.unit_price)
        total_amount = (quantity * unit_price).quantize(
            _MONEY_PRECISION, rounding=ROUND_HALF_UP
        )
        if completed.commercial_snapshot is not None:
            snapshot = completed.commercial_snapshot
            total_amount = CommercialSaleService(self.db).finalize_simulation_payment(
                snapshot, quantity
            )
            unit_price = snapshot.applied_unit_price
            commercial_values = {
                "customer_id": snapshot.customer_id,
                "fleet_id": snapshot.fleet_id,
                "fleet_group_id": snapshot.fleet_group_id,
                "vehicle_id": snapshot.vehicle_id,
                "driver_id": snapshot.driver_id,
                "fuel_card_id": snapshot.fuel_card_id,
                "list_unit_price": snapshot.list_unit_price,
                "discount_rate": snapshot.discount_rate,
                "payment_type": snapshot.payment_type,
            }
        return Sale(
            station_id=completed.station_id,
            tank_id=completed.tank_id,
            pump_id=completed.pump_id,
            fuel_type_id=completed.fuel_type_id,
            simulation_run_id=run.id,
            # Generator identifiers restart for every in-memory runner.  The
            # database identifier is global, so scope it by its persisted run.
            simulation_sale_id=f"{run.id}-{completed.sale_id}",
            sale_timestamp=completed.last_updated_at,
            quantity_liters=quantity,
            unit_price=unit_price,
            total_amount=total_amount,
            nozzle_id=completed.nozzle_id,
            attendant_id=completed.attendant_id,
            shift_id=completed.shift_id,
            start_totalizer_liters=start_totalizer,
            end_totalizer_liters=end_totalizer,
            duration_seconds=int(
                max(0, (completed.last_updated_at - completed.started_at).total_seconds())
            ),
            level_before=_decimal(level_after) + quantity,
            level_after=_decimal(level_after),
            is_anomaly=False,
            **commercial_values,
        )

    def _deliveries(self, run: SimulationRun, result: SimulationTickResult) -> list[Delivery]:
        return [
            Delivery(
                tank_id=item.tank_id,
                simulation_run_id=run.id,
                simulation_delivery_id=item.delivery_id,
                delivery_timestamp=item.delivery_timestamp,
                quantity_liters=_decimal(item.delivered_quantity_liters),
                level_before=_decimal(item.level_before_liters),
                level_after=_decimal(item.level_after_liters),
                supplier_name=item.supplier_name or "Simulation supplier",
            )
            for item in result.deliveries
        ]

    def _update_nozzle_totalizers(
        self, completed_sales: list[ActiveSaleState]
    ) -> None:
        """Add completed sale quantities in the current sale-persistence transaction."""

        deltas: dict[int, Decimal] = {}
        for sale in completed_sales:
            if sale.nozzle_id is None:
                continue
            deltas[sale.nozzle_id] = deltas.get(sale.nozzle_id, Decimal("0")) + _sale_quantity(
                sale.dispensed_quantity_liters
            )
        for nozzle_id, delta in deltas.items():
            nozzle = self.db.scalar(
                select(Nozzle).where(Nozzle.id == nozzle_id).with_for_update()
            )
            if nozzle is None:
                raise ValueError(f"Nozzle {nozzle_id} was not found.")
            nozzle.totalizer_liters += delta

    @staticmethod
    def _events(run: SimulationRun, result: SimulationTickResult) -> list[SimulationEvent]:
        return [
            SimulationEvent(
                simulation_run_id=run.id,
                station_id=event.station_id,
                sequence_number=result.sequence_number,
                event_type=event.event_type,
                event_timestamp=event.event_timestamp,
                target_type=event.target_type,
                target_id=str(event.target_id) if event.target_id is not None else None,
                payload=event.payload,
            )
            for event in result.events
        ]

    def _update_tank_levels(self, result: SimulationTickResult) -> None:
        self._update_tank_states(result.station_id, result.tank_results)

    def _evaluate_alarms(self, run: SimulationRun, result: SimulationTickResult, readings: list[SensorReading]) -> list[object]:
        """Keep alarms in the same transaction as the readings that explain them."""
        if not self._alarms_available:
            return []
        candidates = self._alarms.candidates(
            station_id=run.station_id, tanks=result.tank_results, pumps=result.pump_results,
            readings=readings, moment=result.simulation_time,
            delivery_tank_ids={item.tank_id for item in result.deliveries},
        )
        if not self._models_available:
            return self._alarms.raise_candidates(candidates)
        result.ai_results = LiveAnomalyService(self.db).evaluate(readings, candidates)
        by_target = {(item.entity_type, item.entity_id): item for item in result.ai_results}
        for reading in readings:
            target = ("PUMP", reading.pump_id) if reading.pump_id is not None else ("TANK", reading.tank_id)
            ai_result = by_target.get(target)
            if ai_result is None:
                continue
            reading.is_anomaly = ai_result.is_anomaly
            reading.anomaly_score = None if ai_result.risk_score is None else _decimal(ai_result.risk_score)
            reading.anomaly_type = None if ai_result.anomaly_type is None else AnomalyType(ai_result.anomaly_type)
        return self._alarms.raise_candidates(candidates, by_target)

    def _update_tank_states(self, station_id: int, tank_states: list[object]) -> None:
        """Store the final physical level for each supplied in-memory tank state."""

        for tank_state in tank_states:
            tank = self._tanks.get_for_update(tank_state.tank_id)
            if tank is None:
                raise ValueError(f"Tank {tank_state.tank_id} was not found.")
            if tank.station_id != station_id:
                raise ValueError(f"Tank {tank_state.tank_id} belongs to another station.")
            tank.current_level_liters = _decimal(tank_state.true_level_liters)


def persist_tick(db: Session, run_id: int, result: SimulationTickResult) -> bool:
    """Persist one tick through the standard atomic persistence implementation."""

    return TickPersistence(db).persist(run_id, result)
