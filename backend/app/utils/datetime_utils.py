"""Timezone-aware date and time utilities."""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""

    return datetime.now(timezone.utc)
