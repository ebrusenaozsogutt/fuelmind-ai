from datetime import datetime, timezone
import pytest
from app.simulation import SimulationTickEvent, SimulationTickResult

T = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_tick_basics_and_lists():
    first = SimulationTickResult(1, T, 1)
    second = SimulationTickResult(1, T, 2)
    assert not first.has_activity and first.tank_results is not second.tank_results
    assert (first.tank_count, first.pump_count, first.event_count) == (0, 0, 0)


@pytest.mark.parametrize("station,sequence", [(0, 1), (1, 0), (1, -1)])
def test_tick_rejects_invalid_ids(station, sequence):
    with pytest.raises(ValueError):
        SimulationTickResult(station, T, sequence)


def test_tick_rejects_naive_time():
    with pytest.raises(ValueError):
        SimulationTickResult(1, T.replace(tzinfo=None), 1)


def test_event_validation_and_payload_copy():
    payload = {"x": 1}
    event = SimulationTickEvent("SALE_STARTED", 1, T, payload=payload)
    payload["x"] = 2
    assert event.payload["x"] == 1
    for args in [("", 1, T), ("X", 0, T), ("X", 1, T.replace(tzinfo=None))]:
        with pytest.raises(ValueError):
            SimulationTickEvent(*args)
