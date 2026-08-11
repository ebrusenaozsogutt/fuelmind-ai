"""Tests for persisted SimulationRun runtime configuration."""

from app.models.simulation_run import SimulationRun
from app.simulation.dependencies import simulation_config_from_run
from app.simulation.random_source import RandomSource
from app.utils.enums import SimulationMode, SimulationStatus
from app.utils.simulation_defaults import (
    DEFAULT_PERSIST_EVERY_N_TICKS,
    DEFAULT_RANDOM_SEED,
    DEFAULT_SIMULATION_STEP_SECONDS,
    DEFAULT_SPEED_MULTIPLIER,
    DEFAULT_TICK_INTERVAL_MS,
)


def _run(**values: object) -> SimulationRun:
    return SimulationRun(
        id=1,
        station_id=1,
        status=SimulationStatus.CREATED,
        sequence_number=0,
        generated_sensor_count=0,
        generated_sale_count=0,
        generated_delivery_count=0,
        **values,
    )


def test_simulation_run_uses_canonical_runtime_defaults() -> None:
    """Model construction and SimulationConfig share one set of default values."""

    run = _run()

    assert run.mode == SimulationMode.REALTIME
    assert run.tick_interval_ms == DEFAULT_TICK_INTERVAL_MS
    assert run.simulation_step_seconds == DEFAULT_SIMULATION_STEP_SECONDS
    assert run.speed_multiplier == DEFAULT_SPEED_MULTIPLIER
    assert run.random_seed == DEFAULT_RANDOM_SEED
    assert run.persist_every_n_ticks == DEFAULT_PERSIST_EVERY_N_TICKS


def test_all_persisted_modes_are_supported() -> None:
    """Each declared mode remains storable on a SimulationRun."""

    assert _run(mode=SimulationMode.REALTIME).mode == SimulationMode.REALTIME
    assert _run(mode=SimulationMode.ACCELERATED).mode == SimulationMode.ACCELERATED
    assert _run(mode=SimulationMode.DATASET).mode == SimulationMode.DATASET


def test_persisted_config_bootstraps_stage_three_runtime_settings() -> None:
    """Runner dependencies consume persisted interval, step, seed, and frequency."""

    run = _run(
        mode=SimulationMode.ACCELERATED,
        tick_interval_ms=250,
        simulation_step_seconds=30,
        speed_multiplier=4.5,
        random_seed=99,
        persist_every_n_ticks=7,
    )

    config = simulation_config_from_run(run)

    assert config.tick_interval_seconds == 0.25
    assert config.simulation_step_seconds == 30
    assert config.speed_multiplier == 4.5
    assert config.random_seed == 99
    assert config.persist_every_n_ticks == 7
    assert RandomSource(config.random_seed).random() == RandomSource(99).random()
