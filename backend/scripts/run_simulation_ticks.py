"""Run a deterministic in-memory FuelMind simulation demo."""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.simulation import (
    DeliveryGenerator,
    DemandProfile,
    PumpGenerator,
    PumpState,
    RandomSource,
    SalesGenerator,
    SimulationClock,
    SimulationConfig,
    SimulationValidator,
    StationSimulationState,
    TankGenerator,
    TankState,
    TickEngine,
)
from app.utils.enums import PumpStatus


def build_demo_engine_and_state(seed: int = 42):
    config = SimulationConfig(simulation_step_seconds=5, random_seed=seed)
    random = RandomSource(seed)
    state = StationSimulationState(1)
    for i, (cap, level) in enumerate(
        ((30000, 20000), (25000, 16000), (20000, 12000)), 1
    ):
        state.add_tank(
            TankState(
                i, 1, i, f"T-{i}", cap, level, level, cap * 0.2, cap * 0.1, 20, 0, "OK"
            )
        )
        state.add_pump(PumpState(i, 1, i, i, f"P-{i}", PumpStatus.IDLE, 42, 10, 20, 8))
    engine = TickEngine(
        config=config,
        clock=SimulationClock(config, datetime(2026, 8, 6, 10, tzinfo=timezone.utc)),
        sales_generator=SalesGenerator(
            random_source=random, demand_profile=DemandProfile()
        ),
        tank_generator=TankGenerator(random_source=random),
        pump_generator=PumpGenerator(random_source=random),
        delivery_generator=DeliveryGenerator(random_source=random),
        validator=SimulationValidator(),
        fuel_codes_by_id={1: "DIESEL", 2: "GASOLINE", 3: "LPG"},
        unit_prices_by_fuel={"DIESEL": 45.0, "GASOLINE": 46.0, "LPG": 25.0},
        base_sale_probability=0.3,
    )
    return engine, state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticks", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    engine, state = build_demo_engine_and_state(args.seed)
    for _ in range(args.ticks):
        result = engine.run_tick(state)
        print(
            f"Tick {result.sequence_number:02d} | Time {result.simulation_time.isoformat()} | Active sales {len(state.active_sales)} | Completed {result.completed_sale_count} | Deliveries {result.delivery_count}"
        )
        for tank in result.tank_results:
            print(
                f"Tank {tank.tank_id} | true={tank.true_level_liters:.2f} | measured={tank.measured_level_liters:.2f}"
            )
        for pump in result.pump_results:
            print(
                f"Pump {pump.pump_id} | {pump.status.value} | flow={pump.flow_rate:.2f} | pressure={pump.pressure:.2f} | current={pump.motor_current:.2f}"
            )
    print(f"{args.ticks} ticks completed successfully.")
    print(f"Final sequence: {state.sequence_number}")


if __name__ == "__main__":
    main()
