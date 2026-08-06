"""Virtual UTC clock used by simulation runs."""
#bilgisayarın gerçek saatinden ayrı çalışan bir saat simülasyonu için kullanılır.
from datetime import datetime, timedelta, timezone

from app.simulation.config import SimulationConfig
from app.utils.datetime_utils import utc_now


class SimulationClock:
    """Advance virtual UTC time without waiting on wall-clock time."""

    def __init__(
        self,
        config: SimulationConfig | None = None,
        start_time: datetime | None = None,
    ) -> None:
        """Initialize the clock at an aware start time or the current UTC time."""

        if start_time is not None and (
            start_time.tzinfo is None or start_time.utcoffset() is None
        ):
            raise ValueError("start_time must include a timezone.")

        self._config = config or SimulationConfig()
        self._current_time = (start_time or utc_now()).astimezone(timezone.utc)
        self._speed_multiplier = self._config.speed_multiplier
        self._is_paused = False

    @property
    def current_time(self) -> datetime:
        """Return the current virtual time in UTC."""

        return self._current_time

    @property
    def is_paused(self) -> bool:
        """Return whether virtual time advancement is paused."""

        return self._is_paused

    @property
    def speed_multiplier(self) -> float:
        """Return the active virtual-time speed multiplier."""

        return self._speed_multiplier

    def advance(self) -> datetime:
        """Advance virtual time by one configured step and return it."""

        if not self._is_paused:
            seconds = self._config.simulation_step_seconds * self._speed_multiplier
            self._current_time += timedelta(seconds=seconds)
        return self._current_time

    def pause(self) -> None:
        """Pause virtual time advancement."""

        self._is_paused = True

    def resume(self) -> None:
        """Resume virtual time advancement."""

        self._is_paused = False

    def set_speed(self, speed_multiplier: float) -> None:
        """Set a positive speed multiplier for subsequent advances."""

        if speed_multiplier <= 0:
            raise ValueError("speed_multiplier must be greater than zero.")
        self._speed_multiplier = speed_multiplier
