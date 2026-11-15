from __future__ import annotations

import sys
import logging

from logging.handlers import RotatingFileHandler
from pathlib import Path


LOGGER_NAME = "flightengine"


class FlightEngineFormatter(logging.Formatter):
    LEVEL_COLOURS = {
        "DEBUG": "\033[90m",
        "INFO": "\033[94m",
        "WARNING": "\033[93m",
        "ERROR": "\033[91m",
        "CRITICAL": "\033[91;1m",
    }

    RESET = "\033[0m"

    def __init__(self, use_colour: bool = False):
        super().__init__(
            fmt=(
                "%(asctime)s | %(levelname)-7s | "
                "%(name)s | %(message)s"
            ),
            datefmt="%H:%M:%S",
        )
        self.use_colour = use_colour

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)

        if not self.use_colour:
            return formatted

        colour = self.LEVEL_COLOURS.get(
            record.levelname, ""
        )

        return f"{colour}{formatted}{self.RESET}"


def configure_logging(
    level: str = "INFO",
    log_directory: str | Path | None = None,
) -> logging.Logger:
    log_level = getattr(
        logging,
        level.upper(),
        logging.INFO,
    )

    # Suppress routine dependency logging.
    for name in (
        "sqlalchemy",
        "sqlalchemy.engine",
        "sqlalchemy.pool",
        "sqlalchemy.orm",
        "aiosqlite",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(log_level)
    logger.propagate = False

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(log_level)
    console.setFormatter(
        FlightEngineFormatter(
            use_colour=bool(
                hasattr(sys.stdout, "isatty")
                and sys.stdout.isatty()
            )
        )
    )
    logger.addHandler(console)

    if log_directory is not None:
        directory = Path(log_directory)
        directory.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            directory / "flightengine.log",
            maxBytes=5_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(
            FlightEngineFormatter(use_colour=False)
        )
        logger.addHandler(file_handler)

    return logger


def get_logger(component: str) -> logging.Logger:
    return logging.getLogger(
        f"{LOGGER_NAME}.{component}"
    )

setup_logging = configure_logging