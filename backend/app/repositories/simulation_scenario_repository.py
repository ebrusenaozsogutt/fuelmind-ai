"""Persistence operations for scenarios attached to a simulation run."""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.simulation_scenario import SimulationScenario
from app.utils.enums import SimulationStatus


class SimulationScenarioRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, values: dict[str, object]) -> SimulationScenario:
        entity = SimulationScenario(**values)
        self.db.add(entity)
        self.db.flush()
        return entity

    def list_for_run(self, run_id: int) -> list[SimulationScenario]:
        return list(self.db.scalars(select(SimulationScenario).where(
            SimulationScenario.simulation_run_id == run_id
        ).order_by(SimulationScenario.start_time, SimulationScenario.id)))

    def get_for_run(self, run_id: int, scenario_id: int) -> SimulationScenario | None:
        return self.db.scalar(select(SimulationScenario).where(
            SimulationScenario.simulation_run_id == run_id,
            SimulationScenario.id == scenario_id,
        ))

    def delete(self, scenario: SimulationScenario) -> None:
        self.db.delete(scenario)
        self.db.flush()

    def sync_for_time(self, run_id: int, moment: datetime) -> list[SimulationScenario]:
        """Use virtual simulation time to transition and return active scenarios."""
        scenarios = self.list_for_run(run_id)
        active: list[SimulationScenario] = []
        for scenario in scenarios:
            ends_at = scenario.start_time + timedelta(minutes=scenario.duration_minutes)
            status = (
                SimulationStatus.CREATED if moment < scenario.start_time else
                SimulationStatus.RUNNING if moment < ends_at else SimulationStatus.COMPLETED
            )
            if scenario.status != status:
                scenario.status = status
            if status == SimulationStatus.RUNNING:
                active.append(scenario)
        self.db.flush()
        return active
