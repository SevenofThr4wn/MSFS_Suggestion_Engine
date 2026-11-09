from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.repositories.schedule_repository import (
    ScheduleRepository,
)
from app.db.session import get_db
from app.engines.operations_engine import OperationsEngine
from app.schemas.schedule import (
    ScheduleLookupRequest,
    ScheduleLookupResponse,
)


router = APIRouter(
    prefix="/schedules",
    tags=["Airline Operations & Schedules"],
)

logger = get_logger("api.schedules")


@router.post(
    "/lookup",
    response_model=ScheduleLookupResponse,
)
def lookup_schedule(
    request: ScheduleLookupRequest,
    db: Annotated[Session, Depends(get_db)],
) -> ScheduleLookupResponse:
    """Find documented scheduled flights for an airport pair."""
    logger.info(
        "SCHEDULE REQUEST | %s -> %s | date=%s",
        request.departure_icao,
        request.arrival_icao,
        request.departure_date,
    )

    try:
        repository = ScheduleRepository(db)

        schedules = repository.list_for_route(
            departure_icao=request.departure_icao,
            arrival_icao=request.arrival_icao,
            airline_icao=request.airline_icao,
        )

        result = OperationsEngine(schedules).lookup(request)

        logger.info(
            "SCHEDULE COMPLETE | %s -> %s | matches=%d | status=%s",
            result.departure_icao,
            result.arrival_icao,
            len(result.matches),
            result.status.value,
        )

        return result

    except SQLAlchemyError as exc:
        logger.exception(
            "SCHEDULE DATABASE ERROR | %s -> %s",
            request.departure_icao,
            request.arrival_icao,
        )

        raise HTTPException(
            status_code=503,
            detail="Schedule database is unavailable.",
        ) from exc
