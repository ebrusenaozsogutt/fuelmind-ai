"""Human-readable, deterministic alarm guidance (not ML diagnostics)."""

from typing import Final

CauseList = list[dict[str, str]]
Template = tuple[str, str, CauseList]
DEFAULT: Final[Template] = (
    "An operational value exceeded its configured rule threshold.",
    "Check the affected equipment and its latest sensor readings.",
    [{"description": "Operational value outside its configured rule threshold"}],
)


def _causes(*items: str) -> CauseList:
    return [{"description": item} for item in items]


_TEMPLATES: Final[dict[str, Template]] = {
    "LOW_FLOW": ("Pump flow is below its configured minimum while the pump is active.", "Check the pump filter, line pressure and pump performance.", _causes("Filter blockage", "Pump performance loss", "Line pressure problem")),
    "HIGH_MOTOR_CURRENT": ("Pump motor current exceeds the configured operating limit.", "Check motor load, mechanical friction and pump operating conditions.", _causes("Excess motor load", "Mechanical friction", "Pump wear")),
    "HIGH_PRESSURE": ("Pump line pressure exceeds the configured maximum.", "Check line pressure, valve state and possible blockages.", _causes("Closed valve", "Line blockage", "Pressure sensor deviation")),
    "HIGH_WATER_LEVEL": ("Tank water level is above the critical operating threshold.", "Verify the tank water level and inspect fuel/water separation.", _causes("Water contamination", "Tank sealing issue", "Level sensor verification needed")),
    "SENSOR_STUCK": ("Measured tank level stayed unchanged for a meaningful period while sales continued.", "Check the tank level sensor and sensor communication.", _causes("Stuck sensor", "Communication problem", "Calibration needed")),
    "SENSOR_SPIKE": ("A sudden measured value change cannot be explained by the physical flow.", "Verify the measurement change; check sensor connection and calibration.", _causes("Connection interruption", "Electrical noise", "Sensor calibration")),
    "TANK_SALES_MISMATCH": ("Tank level decrease is greater than the amount explained by sales.", "Compare sales records with tank level; investigate a possible leak or measurement error.", _causes("Record mismatch", "Possible leak", "Level measurement error")),
    "LOW_DATA_QUALITY": ("A data quality issue was detected in readings from the affected equipment.", "Check sensor data, communication and recent quality flags.", _causes("Communication interruption", "Missing data", "Physical range violation")),
}


def guidance_for(alarm_type: str) -> Template:
    return _TEMPLATES.get(alarm_type, DEFAULT)
