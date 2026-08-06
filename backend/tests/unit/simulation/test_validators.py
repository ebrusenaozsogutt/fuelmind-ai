import pytest
from app.simulation import SimulationValidator, TankState, PumpState
from app.utils.enums import PumpStatus


def tank():
    return TankState(1, 1, 1, "T", 100, 50, 50, 10, 5, 20, 0, "OK")


def pump():
    return PumpState(1, 1, 1, 1, "P", PumpStatus.IDLE, 10, 1, 10, 10)


def test_valid_states():
    v = SimulationValidator()
    v.validate_tank_state(tank())
    v.validate_pump_state(pump())


@pytest.mark.parametrize(
    "field,value",
    [
        ("true_level_liters", -1),
        ("measured_level_liters", 101),
        ("temperature", float("nan")),
        ("water_level", float("inf")),
    ],
)
def test_invalid_tank(field, value):
    item = tank()
    setattr(item, field, value)
    with pytest.raises(ValueError):
        SimulationValidator().validate_tank_state(item)


@pytest.mark.parametrize(
    "field,value", [("flow_rate", -1), ("pressure", float("nan")), ("status", "BAD")]
)
def test_invalid_pump(field, value):
    item = pump()
    setattr(item, field, value)
    with pytest.raises(ValueError):
        SimulationValidator().validate_pump_state(item)
