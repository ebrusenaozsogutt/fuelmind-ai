"""Central logging configuration for the backend application."""

import logging


def configure_logging(log_level: str) -> None:
    """Configure the root logger using the supplied level name."""

    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        force=True,
    )
