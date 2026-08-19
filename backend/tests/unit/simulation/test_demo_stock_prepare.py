"""Regression coverage for demo stock preparation's active-run guard."""

import pytest

from app.simulation.lifecycle import is_station_run_blocking
from app.utils.enums import SimulationMode, SimulationStatus


def _blocking(status: SimulationStatus, *, runner_is_active: bool = False) -> bool:
    return is_station_run_blocking(
        mode=SimulationMode.REALTIME,
        status=status,
        runner_is_active=runner_is_active,
    )


def test_demo_stock_prepare_allows_no_active_run() -> None:
    assert not _blocking(SimulationStatus.RUNNING)


def test_demo_stock_prepare_ignores_failed_run() -> None:
    assert not _blocking(SimulationStatus.FAILED)


def test_demo_stock_prepare_ignores_completed_run() -> None:
    assert not _blocking(SimulationStatus.COMPLETED)


def test_demo_stock_prepare_ignores_stopped_run() -> None:
    assert not _blocking(SimulationStatus.STOPPED)


def test_demo_stock_prepare_handles_stale_waiting_run() -> None:
    # The current lifecycle calls the pre-start state CREATED.  Legacy
    # WAITING-like rows have no owned runner and therefore do not lock a station.
    assert not _blocking(SimulationStatus.CREATED)


def test_demo_stock_prepare_blocks_running_run() -> None:
    assert _blocking(SimulationStatus.RUNNING, runner_is_active=True)


def test_demo_stock_prepare_blocks_paused_run() -> None:
    assert _blocking(SimulationStatus.PAUSED, runner_is_active=True)


@pytest.mark.parametrize(
    "status",
    [SimulationStatus.STARTING, SimulationStatus.STOPPING],
)
def test_manager_owned_lifecycle_transitions_remain_blocking(
    status: SimulationStatus,
) -> None:
    assert _blocking(status, runner_is_active=True)
