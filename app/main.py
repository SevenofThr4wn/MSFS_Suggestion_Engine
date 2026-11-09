from __future__ import annotations

import logging
import os

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import inspect

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.session import engine


def ensure_logging_configured() -> None:
    """Configure logging unless the launcher already has."""
    if logging.getLogger("flightengine").handlers:
        return

    configure_logging(
        level=os.getenv("FLIGHTENGINE_LOG_LEVEL", "INFO"),
        log_directory=Path.cwd() / "logs",
    )


def verify_database() -> None:
    """Verify that the configured database is usable."""
    logger = get_logger("server")

    logger.info(
        "DATABASE | url=%s",
        engine.url.render_as_string(hide_password=True),
    )

    tables = set(inspect(engine).get_table_names())

    if "aircraft" not in tables:
        raise RuntimeError(
            "FlightEngine database is missing the aircraft table. "
            "Verify DATABASE_URL and the database location."
        )

    logger.info(
        "DATABASE | verified | tables=%d | aircraft table found",
        len(tables),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    ensure_logging_configured()

    logger = get_logger("server")

    logger.info(
        "STARTUP | application=%s | version=%s | environment=%s",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.APP_ENV,
    )

    try:
        verify_database()
    except Exception:
        logger.exception(
            "STARTUP FAILED | Database verification unsuccessful"
        )
        raise

    try:
        yield
    finally:
        logger.info(
            "SHUTDOWN | application=%s",
            settings.APP_NAME,
        )

        engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    description=settings.APP_DESCRIPTION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/", tags=["System"])
def root() -> dict[str, str]:
    """Return basic application information."""
    return {
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
    }
