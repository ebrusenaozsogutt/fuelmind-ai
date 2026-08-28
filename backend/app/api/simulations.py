"""REST operations for persisted simulation runs and lifecycle commands."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin, require_operator_or_admin
from app.database import get_db
from app.exceptions import BusinessRuleError, NotFoundError
from app.models.user import User
from app.models.pump import Pump
from app.models.tank import Tank
from app.repositories.simulation_run_repository import SimulationRunRepository
from app.repositories.simulation_scenario_repository import SimulationScenarioRepository
from app.repositories.station_repository import StationRepository
from app.schemas.simulation_run import (
    DatasetGenerationCreate,
    SimulationRunCreate,
    SimulationRunRead,
    SimulationRunStatistics,
)
from app.schemas.simulation_scenario import SimulationScenarioCreate, SimulationScenarioRead
from app.simulation.manager import SimulationManager
from app.utils.enums import ScenarioType, SimulationMode, SimulationStatus, SimulationTargetType

router = APIRouter(prefix="/simulations", tags=["simulations"])


def get_simulation_manager(request: Request) -> SimulationManager:
    """Return the lifespan-owned process manager without creating a new instance."""

    try:
        return request.app.state.simulation_manager
    except AttributeError as exc:
        raise BusinessRuleError("Simulation manager is not available.") from exc


def _get_run(db: Session, run_id: int):
    run = SimulationRunRepository(db).get(run_id)
    if run is None:
        raise NotFoundError("Simulation run not found.")
    return run


def _validate_scenario_target(db: Session, run: object, payload: SimulationScenarioCreate) -> None:
    allowed_targets = {
        ScenarioType.FLOW_DROP: {SimulationTargetType.STATION, SimulationTargetType.PUMP},
        ScenarioType.HIGH_MOTOR_CURRENT: {SimulationTargetType.STATION, SimulationTargetType.PUMP},
        ScenarioType.TANK_LEAK: {SimulationTargetType.STATION, SimulationTargetType.TANK},
        ScenarioType.SENSOR_STUCK: {SimulationTargetType.STATION, SimulationTargetType.TANK},
        ScenarioType.SENSOR_SPIKE: {SimulationTargetType.STATION, SimulationTargetType.TANK},
        ScenarioType.WATER_LEVEL_RISE: {SimulationTargetType.STATION, SimulationTargetType.TANK},
        ScenarioType.DEMAND_SURGE: {SimulationTargetType.STATION},
    }
    if payload.target_type not in allowed_targets[payload.scenario_type]:
        raise BusinessRuleError("Scenario type is incompatible with its target type.")
    if payload.target_type == SimulationTargetType.STATION:
        if payload.target_id != run.station_id:
            raise BusinessRuleError("Station scenario target must be the run station.")
        return
    target_model = Tank if payload.target_type == SimulationTargetType.TANK else Pump
    target = db.get(target_model, payload.target_id)
    if target is None or target.station_id != run.station_id:
        raise BusinessRuleError("Scenario target must belong to the run station.")


@router.post("/{run_id}/scenarios", response_model=SimulationScenarioRead, status_code=status.HTTP_201_CREATED)
def create_scenario(
    run_id: int,
    payload: SimulationScenarioCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    run = _get_run(db, run_id)
    _validate_scenario_target(db, run, payload)
    try:
        scenario = SimulationScenarioRepository(db).create({
            **payload.model_dump(), "simulation_run_id": run_id, "status": SimulationStatus.CREATED
        })
        db.commit()
        db.refresh(scenario)
        return scenario
    except Exception:
        db.rollback()
        raise


@router.get("/{run_id}/scenarios", response_model=list[SimulationScenarioRead])
def list_scenarios(
    run_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> list[object]:
    _get_run(db, run_id)
    return SimulationScenarioRepository(db).list_for_run(run_id)


@router.delete("/{run_id}/scenarios/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario(
    run_id: int,
    scenario_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> None:
    _get_run(db, run_id)
    scenario = SimulationScenarioRepository(db).get_for_run(run_id, scenario_id)
    if scenario is None:
        raise NotFoundError("Simulation scenario not found.")
    try:
        SimulationScenarioRepository(db).delete(scenario)
        db.commit()
    except Exception:
        db.rollback()
        raise


@router.post("", response_model=SimulationRunRead, status_code=status.HTTP_201_CREATED)
def create_simulation(
    payload: SimulationRunCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
) -> object:
    """Create a CREATED run without scheduling its runner."""

    station = StationRepository(db).get(payload.station_id)
    if station is None:
        raise NotFoundError("Station not found.")
    if not station.is_active:
        raise BusinessRuleError("Cannot create a simulation for an inactive station.")
    values = payload.model_dump()
    values.update(
        {
            "status": SimulationStatus.CREATED,
            "current_simulation_time": payload.simulation_start_time,
            "sequence_number": 0,
            "generated_sensor_count": 0,
            "generated_sale_count": 0,
            "generated_delivery_count": 0,
            "created_by": current_user.id,
        }
    )
    repository = SimulationRunRepository(db)
    try:
        run = repository.create(values)
        db.commit()
        db.refresh(run)
        return run
    except Exception:
        db.rollback()
        raise


@router.post("/start-new", response_model=SimulationRunRead, status_code=status.HTTP_201_CREATED)
async def start_new_simulation(
    payload: SimulationRunCreate,
    db: Annotated[Session, Depends(get_db)],
    manager: Annotated[SimulationManager, Depends(get_simulation_manager)],
    current_user: Annotated[User, Depends(require_admin)],
) -> object:
    """Stop the active station run, then create and start an isolated new run.

    This is intentionally distinct from ``/{run_id}/resume``: a new row has
    fresh counters and a fresh clock, while resume retains the existing row.
    """

    if payload.mode != SimulationMode.REALTIME:
        raise BusinessRuleError("Start new is available only for REALTIME simulations.")
    station = StationRepository(db).get(payload.station_id)
    if station is None:
        raise NotFoundError("Station not found.")
    if not station.is_active:
        raise BusinessRuleError("Cannot create a simulation for an inactive station.")

    await manager.stop_active_realtime_run(payload.station_id)
    values = payload.model_dump()
    values.update(
        {
            "status": SimulationStatus.CREATED,
            "current_simulation_time": payload.simulation_start_time,
            "sequence_number": 0,
            "generated_sensor_count": 0,
            "generated_sale_count": 0,
            "generated_delivery_count": 0,
            "created_by": current_user.id,
        }
    )
    try:
        run = SimulationRunRepository(db).create(values)
        db.commit()
        run_id = run.id
    except Exception:
        db.rollback()
        raise
    await manager.start_run(run_id)
    db.expire_all()
    return _get_run(db, run_id)


@router.post(
    "/datasets/generate", response_model=SimulationRunRead, status_code=status.HTTP_201_CREATED
)
async def generate_dataset(
    payload: DatasetGenerationCreate,
    db: Annotated[Session, Depends(get_db)],
    manager: Annotated[SimulationManager, Depends(get_simulation_manager)],
    current_user: Annotated[User, Depends(require_admin)],
) -> object:
    """Persist and schedule a historical dataset run, returning immediately."""

    station = StationRepository(db).get(payload.station_id)
    if station is None:
        raise NotFoundError("Station not found.")
    if not station.is_active:
        raise BusinessRuleError("Cannot create a simulation for an inactive station.")
    repository = SimulationRunRepository(db)
    try:
        run = repository.create(
            {
                "station_id": payload.station_id,
                "mode": SimulationMode.DATASET,
                "status": SimulationStatus.CREATED,
                "simulation_start_time": payload.simulation_start_time,
                "target_simulation_time": payload.target_simulation_time,
                "current_simulation_time": payload.simulation_start_time,
                "simulation_step_seconds": payload.simulation_step_seconds,
                "random_seed": payload.random_seed,
                "sequence_number": 0,
                "generated_sensor_count": 0,
                "generated_sale_count": 0,
                "generated_delivery_count": 0,
                "created_by": current_user.id,
            }
        )
        db.commit()
        db.refresh(run)
    except Exception:
        db.rollback()
        raise
    await manager.start_dataset_run(run.id, payload.days)
    db.expire_all()
    return _get_run(db, run.id)


@router.get("", response_model=list[SimulationRunRead])
def list_simulations(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    station_id: int | None = None,
    status_filter: Annotated[SimulationStatus | None, Query(alias="status")] = None,
    mode: SimulationMode | None = None,
) -> list[object]:
    """List runs with optional station, status, and mode filtering."""

    return SimulationRunRepository(db).list(
        station_id=station_id,
        status=status_filter,
        mode=mode,
    )


@router.get("/active", response_model=SimulationRunRead | None)
def get_active_simulation(
    station_id: int,
    db: Annotated[Session, Depends(get_db)],
    manager: Annotated[SimulationManager, Depends(get_simulation_manager)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> object | None:
    """Return only a manager-owned realtime run, never a DB-only lifecycle row."""

    run_id = manager.active_run_id_for_station(station_id)
    return None if run_id is None else _get_run(db, run_id)


@router.get("/{run_id}", response_model=SimulationRunRead)
def get_simulation(
    run_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> object:
    """Return one persisted simulation run."""

    return _get_run(db, run_id)


@router.post("/{run_id}/start", response_model=SimulationRunRead)
async def start_simulation(
    run_id: int,
    db: Annotated[Session, Depends(get_db)],
    manager: Annotated[SimulationManager, Depends(get_simulation_manager)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    """Schedule a run and wait for its persisted startup transition."""

    _get_run(db, run_id)
    await manager.start_run(run_id)
    db.expire_all()
    return _get_run(db, run_id)


@router.post("/{run_id}/pause", response_model=SimulationRunRead)
async def pause_simulation(
    run_id: int,
    db: Annotated[Session, Depends(get_db)],
    manager: Annotated[SimulationManager, Depends(get_simulation_manager)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    """Pause an active run through its manager."""

    _get_run(db, run_id)
    await manager.pause_run(run_id)
    db.expire_all()
    return _get_run(db, run_id)


@router.post("/{run_id}/resume", response_model=SimulationRunRead)
async def resume_simulation(
    run_id: int,
    db: Annotated[Session, Depends(get_db)],
    manager: Annotated[SimulationManager, Depends(get_simulation_manager)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    """Resume an active run through its manager."""

    _get_run(db, run_id)
    await manager.resume_run(run_id)
    db.expire_all()
    return _get_run(db, run_id)


@router.post("/{run_id}/stop", response_model=SimulationRunRead)
async def stop_simulation(
    run_id: int,
    db: Annotated[Session, Depends(get_db)],
    manager: Annotated[SimulationManager, Depends(get_simulation_manager)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    """Stop a run and return its terminal persisted state."""

    _get_run(db, run_id)
    await manager.stop_run(run_id)
    db.expire_all()
    return _get_run(db, run_id)


@router.get("/{run_id}/statistics", response_model=SimulationRunStatistics)
def simulation_statistics(
    run_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> SimulationRunStatistics:
    """Return the run's existing counters without aggregate queries."""

    run = _get_run(db, run_id)
    progress_percent: float | None = None
    if run.mode == SimulationMode.DATASET and run.target_simulation_time:
        total = (run.target_simulation_time - run.simulation_start_time).total_seconds()
        current = run.current_simulation_time or run.simulation_start_time
        progress_percent = 100.0 if run.status == SimulationStatus.COMPLETED else (
            0.0 if total <= 0 else max(0.0, min(100.0, 100 * (current - run.simulation_start_time).total_seconds() / total))
        )
    return SimulationRunStatistics(
        run_id=run.id,
        status=run.status,
        current_simulation_time=run.current_simulation_time,
        sequence_number=run.sequence_number,
        generated_sensor_count=run.generated_sensor_count,
        generated_sale_count=run.generated_sale_count,
        generated_delivery_count=run.generated_delivery_count,
        real_started_at=run.real_started_at,
        real_ended_at=run.real_ended_at,
        target_simulation_time=run.target_simulation_time,
        progress_percent=progress_percent,
    )
