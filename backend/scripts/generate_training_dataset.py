"""Generate one bounded historical dataset through the shared manager workflow."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.exceptions import BusinessRuleError, NotFoundError
from app.repositories.simulation_run_repository import SimulationRunRepository
from app.repositories.station_repository import StationRepository
from app.simulation.manager import SimulationManager
from app.utils.datetime_utils import utc_now
from app.utils.enums import SimulationMode, SimulationStatus


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--station-id", type=int, required=True)
    parser.add_argument("--days", type=int, choices=(30, 60, 90), required=True)
    parser.add_argument("--step-seconds", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--start-time", type=datetime.fromisoformat)
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    args.start_time = args.start_time or utc_now()
    if args.station_id <= 0 or args.step_seconds <= 0:
        raise ValueError("station-id and step-seconds must be positive.")
    if args.start_time.tzinfo is None or args.start_time.utcoffset() is None:
        raise ValueError("start-time must include a timezone.")
    session = SessionLocal()
    try:
        station = StationRepository(session).get(args.station_id)
        if station is None:
            raise NotFoundError("Station not found.")
        if not station.is_active:
            raise BusinessRuleError("Cannot create a simulation for an inactive station.")
        run = SimulationRunRepository(session).create(
            {
                "station_id": args.station_id,
                "mode": SimulationMode.DATASET,
                "status": SimulationStatus.CREATED,
                "simulation_start_time": args.start_time,
                "target_simulation_time": args.start_time + timedelta(days=args.days),
                "current_simulation_time": args.start_time,
                "simulation_step_seconds": args.step_seconds,
                "random_seed": args.seed,
                "sequence_number": 0,
                "generated_sensor_count": 0,
                "generated_sale_count": 0,
                "generated_delivery_count": 0,
            }
        )
        session.commit()
        run_id = run.id
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    manager = SimulationManager()
    try:
        await manager.start_dataset_run(run_id, args.days)
        await manager.wait_for_dataset_run(run_id)
    finally:
        await manager.shutdown()
    print(run_id)


if __name__ == "__main__":
    asyncio.run(main())
