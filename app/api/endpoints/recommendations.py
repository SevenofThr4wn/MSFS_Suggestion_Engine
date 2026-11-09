from __future__ import annotations

import logging
import os
import time
from typing import Annotated, Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_airport_catalog
from app.db.session import get_db

try:
    from app.db.repositories.route_catalog_repository import (
        RouteCatalogRepository,
    )
except ImportError:
    from app.db.repositories.route_repository import (
        RouteRepository as RouteCatalogRepository,
    )

from app.core.logging import get_logger
from app.core.recommendation_logging import RecommendationLogger

from app.engines.environment_engine import EnvironmentEngine
from app.engines.airport_engine import AirportEngine
from app.engines.geographic_engine import GeographicEngine
from app.engines.recommendation_engine import RecommendationEngine
from app.engines.route_engine import RouteEngine

from app.api.endpoints.addons import (
    get_addon_inventory_service,
)
from app.schemas.addon_compatibility import (
    AddonCompatibilityRequest,
)
from app.services.addon_compatibility_service import (
    AddonCompatibilityService,
)


from app.db.models.aircraft import Aircraft
from app.db.models.flight_log import FlightLog

from app.providers.airport_catalog import AirportCatalog
from app.providers.airport_location import get_airport_location

from app.schemas.recommendation import (
    RecommendationRequest,
    RecommendationResponse,
)

from app.services.recommendation_schedule_service import (
    RecommendationScheduleService,
)
from app.schemas.schedule import ScheduleStatus


router = APIRouter(
    prefix="/recommendations",
    tags=["Recommendation Engine"],
)

weather_engine = EnvironmentEngine(ttl_seconds=600)

logger = get_logger("api.recommendations")


def log_value(value: Any, fallback: str = "N/A") -> str:
    """Format a value for readable console logging."""
    if value is None:
        return fallback

    if isinstance(value, float):
        return f"{value:.2f}"

    return str(value)


def log_recommendation_results(
    response: RecommendationResponse,
    log: RecommendationLogger,
) -> None:
    """
    Log the recommendations that the engine returned.

    This does not re-evaluate or modify recommendations.
    """

    recommendations = response.recommendations or []

    logger.info(
        "[%s] RESULTS | Logging %d returned recommendations",
        log.request_id,
        len(recommendations),
    )

    for index, item in enumerate(recommendations, start=1):
        route = item.route

        departure = route.departure_icao
        arrival = route.arrival_icao

        aircraft = route.aircraft_name

        duration_minutes = getattr(
            route,
            "estimated_duration_min",
            None,
        )

        duration_hours = (
            duration_minutes / 60
            if duration_minutes is not None
            else None
        )

        logger.info(
            "[%s] ROUTE %02d | %s -> %s | "
            "aircraft=%s | distance_nm=%s | "
            "duration_h=%s",
            log.request_id,
            index,
            departure,
            arrival,
            aircraft,
            log_value(route.distance_nm),
            log_value(duration_hours),
        )

        logger.info(
            "[%s] SCORE %02d | %s -> %s | "
            "flyability=%s | preference=%s | "
            "realism=%s | weather=%s | "
            "novelty=%s | final=%s",
            log.request_id,
            index,
            departure,
            arrival,
            log_value(item.flyability_score),
            log_value(item.preference_score),
            log_value(item.realism_score),
            log_value(item.weather_score),
            log_value(item.history_novelty_score),
            log_value(item.final_score),
        )

        validation = item.aircraft_validation

        logger.info(
            "[%s] VALIDATION %02d | %s -> %s | "
            "status=%s | departure_runway=%s | "
            "arrival_runway=%s",
            log.request_id,
            index,
            departure,
            arrival,
            log_value(
                getattr(validation, "status", None)
            ),
            log_value(
                getattr(validation, "departure_runway", None)
            ),
            log_value(
                getattr(validation, "arrival_runway", None)
            ),
        )

        reasons = item.reasons or []

        for reason in reasons:
            logger.info(
                "[%s] REASON %02d | %s -> %s | %s",
                log.request_id,
                index,
                departure,
                arrival,
                reason,
            )

        warnings = getattr(item, "warnings", None) or []

        for warning in warnings:
            logger.warning(
                "[%s] WARNING %02d | %s -> %s | %s",
                log.request_id,
                index,
                departure,
                arrival,
                warning,
            )

        # Detailed breakdowns appear in DEBUG mode.
        logger.debug(
            "[%s] BREAKDOWN %02d | scores=%s",
            log.request_id,
            index,
            item.score_breakdown,
        )

        logger.debug(
            "[%s] EVIDENCE %02d | coverage=%s",
            log.request_id,
            index,
            item.evidence_coverage,
        )


def log_rejected_examples(
    response: RecommendationResponse,
    log: RecommendationLogger,
) -> None:
    """
    Log rejected examples supplied by the engine.

    These may be only a subset of all rejected candidates.
    """

    rejected = response.rejected_examples or []

    logger.info(
        "[%s] REJECTIONS | %d reported examples",
        log.request_id,
        len(rejected),
    )

    for index, item in enumerate(rejected, start=1):
        departure = getattr(
            item,
            "departure_icao",
            None,
        )

        arrival = getattr(
            item,
            "arrival_icao",
            None,
        )

        aircraft_id = getattr(
            item,
            "aircraft_id",
            None,
        )

        status = getattr(item, "status", None)

        logger.info(
            "[%s] REJECT %02d | %s -> %s | "
            "aircraft_id=%s | status=%s",
            log.request_id,
            index,
            log_value(departure),
            log_value(arrival),
            log_value(aircraft_id),
            log_value(status),
        )

        for issue in getattr(item, "issues", []) or []:
            logger.info(
                "[%s] REJECT REASON %02d | "
                "code=%s | message=%s | "
                "observed=%s | required=%s | unit=%s",
                log.request_id,
                index,
                log_value(getattr(issue, "code", None)),
                log_value(getattr(issue, "message", None)),
                log_value(getattr(issue, "observed", None)),
                log_value(getattr(issue, "required", None)),
                log_value(getattr(issue, "unit", None)),
            )


@router.post(
    "/generate",
    response_model=RecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate Flight Recommendations",
    description=(
        "Generates flight recommendations based on the supplied "
        "aircraft, airport, route, and preference criteria.\n\n"
        "The Recommendation Engine generates candidate routes, evaluates "
        "them, applies its eligibility filters, and returns scored "
        "recommendations. The exact filters and options are defined "
        "by the `RecommendationRequest` schema.\n\n"
        "**Processing overview:**\n"
        "1. Accepts and validates the recommendation parameters.\n"
        "2. Generates and evaluates route candidates.\n"
        "3. Applies the engine's filtering and scoring logic.\n"
        "4. Enriches returned recommendations with departure and "
        "arrival location information.\n"
        "5. Returns the recommendations, processing counts, warnings, "
        "and any additional diagnostics included in the response.\n\n"
        "**Important:** The endpoint is intended for flight simulation "
        "planning; it is not a real-world flight dispatch service. "
        "A successful request may return no eligible recommendations."
    ),
    response_description=(
        "Scored recommendations and generation statistics, "
        "using the RecommendationResponse schema."
    ),
    responses={
        404: {
            "description": (
                "A required resource could not be located during "
                "recommendation generation."
            ),
        },
        422: {
            "description": (
                "Invalid request parameters or a value error "
                "encountered while generating recommendations."
            ),
        },
        500: {
            "description": "An unexpected error occurred during generation.",
        },
    },
)
def generate(
    request: Annotated[
        RecommendationRequest,
        Body(
            description=(
                "Route discovery or point-to-point criteria, including "
                "aircraft, flight duration, airport filters, and preferences."
            ),
        ),
    ],
    db: Annotated[Session, Depends(get_db)],
    catalog: Annotated[
        AirportCatalog,
        Depends(get_airport_catalog),
    ],
):
    """Generate scored flight recommendations and enrich airport locations.

    Args:
        request: Parameters defining the requested flight recommendations.
        db: Database session supplied by FastAPI.
        catalog: Airport catalog supplied by FastAPI.

    Returns:
        RecommendationResponse: Recommendations and processing statistics.

    Raises:
        HTTPException: 404 for missing resources or 422 for value errors.
    """
    request_id = str(uuid4())[:8]

    log = RecommendationLogger(request_id)

    start = time.perf_counter()

    log.start(
        departure=request.departure_code,
        category=request.preferred_category,
        airport_mode=request.airport_mode,
    )

    logger.info(
        "[%s] PARAMETERS | "
        "departure=%s | arrival=%s | "
        "aircraft_id=%s | owned_only=%s | "
        "duration=%s-%s h | limit=%s",
        request_id,
        request.departure_code,
        log_value(request.arrival_code, "ANY"),
        log_value(request.aircraft_id),
        request.owned_only,
        request.min_duration_hours,
        request.max_duration_hours,
        request.limit,
    )

    logger.info(
        "[%s] FILTERS | "
        "addon_scenery=%s | "
        "minimum_flyability=%s | "
        "real_world_service=%s | "
        "strict_aircraft_category=%s | "
        "airport_mode=%s",
        request_id,
        request.prefer_addon_scenery,
        request.min_flyability_score,
        request.require_real_world_service,
        request.strict_aircraft_category,
        request.airport_mode,
    )

    logger.info(
        "[%s] ENGINE | Initialising recommendation engine",
        request_id,
    )

    try:
        engine = RecommendationEngine(
            session=db,
            route_engine=RouteEngine(
                RouteCatalogRepository(db),
                catalog,
            ),
            environment=weather_engine,
        )

        logger.info(
            "[%s] ENGINE | Starting candidate generation "
            "and scoring",
            request_id,
        )

        response = engine.recommend(request)

        
        schedule_matches = (
            RecommendationScheduleService(db).match_routes(
                routes=[
                    item.route
                    for item in response.recommendations
                ],
                departure_date=request.departure_date,
                prefer_scheduled_aircraft=(
                    request.prefer_scheduled_aircraft
                ),
            )
            if request.schedule_enabled
            else [None] * len(response.recommendations)
        )


        inventory = get_addon_inventory_service().scan()
        addon_service = AddonCompatibilityService(inventory)

        # Enrich the final results without changing engine scoring or filtering.
        departure_location = get_airport_location(
            request.departure_code
        )

        
        enriched_recommendations = []

        for item, schedule_match in zip(
            response.recommendations,
            schedule_matches,
        ):
            route = item.route

            compatibility = addon_service.evaluate(
                AddonCompatibilityRequest(
                    aircraft_icao=route.aircraft_icao_code,
                    airline_icao=route.airline_icao,
                    departure_icao=route.departure_icao,
                    arrival_icao=route.arrival_icao,
                )
            )

            enriched_recommendations.append(
                item.model_copy(
                    update={
                        "arrival_location": get_airport_location(
                            route.arrival_icao
                        ),
                        "addon_compatibility": compatibility,
                    }
                )
            )

            
            enriched_recommendations.append(
                item.model_copy(
                    update={
                        "arrival_location": get_airport_location(
                            route.arrival_icao
                        ),
                        "addon_compatibility": compatibility,
                        "schedule": schedule_match,
                        "scheduled_service_verified": (
                            schedule_match is not None
                            and schedule_match.schedule.status
                            == ScheduleStatus.VERIFIED
                            and schedule_match.operates_on_date is True
                        ),
                    }
                )
            )

        if request.schedule_enabled and request.require_scheduled_service:
            enriched_recommendations = [
                item
                for item in enriched_recommendations
                    if item.schedule is not None
                    and item.schedule.operates_on_date is True
                    and item.schedule.schedule.status
                == ScheduleStatus.VERIFIED
            ]

            response = response.model_copy(
                update={
                    "departure_location": departure_location,
                    "recommendations": enriched_recommendations,
                    "returned": len(enriched_recommendations),
                }
            )

        logger.info(
            "[%s] DEPARTURE LOCATION | %s | %s",
            request_id,
            departure_location.icao,
            departure_location.display_name,
        )

        for item in enriched_recommendations:
            logger.info(
                "[%s] ARRIVAL LOCATION | %s | %s",
                request_id,
                item.route.arrival_icao,
                item.arrival_location.display_name,
            )

        logger.info(
            "[%s] ENGINE | Recommendation evaluation completed",
            request_id,
        )

       

        log_recommendation_results(response, log)

        

        log_rejected_examples(response, log)

       

        for warning in response.warnings or []:
            logger.warning(
                "[%s] RESPONSE WARNING | %s",
                request_id,
                warning,
            )

        

        log.response(
            generated=response.generated_candidates,
            evaluated=response.evaluated_routes,
            eligible=response.eligible_after_filters,
            returned=response.returned,
        )

        logger.info(
            "[%s] COMPLETE | elapsed=%.3fs | "
            "generated=%d | evaluated=%d | "
            "eligible=%d | returned=%d",
            request_id,
            time.perf_counter() - start,
            response.generated_candidates,
            response.evaluated_routes,
            response.eligible_after_filters,
            response.returned,
        )

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "[%s] FULL RESPONSE | %s",
                request_id,
                response.model_dump_json(indent=2),
            )

        return response

    except LookupError as exc:
        log.failure(exc)

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        log.failure(exc)

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception:
        logger.exception(
            "[%s] UNEXPECTED ERROR | "
            "Recommendation generation failed",
            request_id,
        )
        raise




class FlightLogCreate(BaseModel):
    """Request body used to record a completed simulator flight."""

    departure_icao: str = Field(
        ...,
        min_length=4,
        max_length=8,
        description="ICAO identifier of the departure airport.",
        examples=["YBBN"],
    )

    arrival_icao: str = Field(
        ...,
        min_length=4,
        max_length=8,
        description="ICAO identifier of the arrival airport.",
        examples=["YSSY"],
    )

    aircraft_id: int = Field(
        ...,
        gt=0,
        description="Unique database ID of the aircraft used for the flight.",
        examples=[1],
    )

    rating: int | None = Field(
        default=None,
        ge=1,
        le=5,
        description=(
            "Optional flight rating from 1 to 5. "
            "Omit or supply null for an unrated flight."
        ),
        examples=[5],
    )


class FlightLogResponse(BaseModel):
    """Newly created flight log entry."""

    id: int = Field(
        ...,
        description="Unique database identifier of the saved flight log.",
        examples=[42],
    )

    departure_icao: str = Field(
        ...,
        description="Resolved ICAO identifier of the departure airport.",
        examples=["YBBN"],
    )

    arrival_icao: str = Field(
        ...,
        description="Resolved ICAO identifier of the arrival airport.",
        examples=["YSSY"],
    )

    aircraft_id: int = Field(
        ...,
        description="Database identifier of the aircraft used.",
        examples=[1],
    )

    rating: int | None = Field(
        ...,
        description="Saved flight rating, or null if no rating was given.",
        examples=[5],
    )

@router.post(
    "/flight-log",
    response_model=FlightLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a Completed Flight",
    description=(
        "Creates a flight log entry for a completed simulator flight.\n\n"
        "**Validation:**\n"
        "- Departure and arrival airports must exist in the airport catalog.\n"
        "- The departure and arrival must resolve to different airports.\n"
        "- The supplied aircraft ID must exist in the database.\n"
        "- If provided, the rating must be between 1 and 5.\n\n"
        "After validation, the flight is saved to the database and "
        "the newly created record is returned.\n\n"
        "**Note:** This endpoint records a flight. It does not "
        "verify that the flight was actually flown."
    ),
    response_description="The newly created flight log entry.",
    responses={
        404: {
            "description": "Departure/arrival airport or aircraft not found.",
            "content": {
                "application/json": {
                    "examples": {
                        "airport_not_found": {
                            "summary": "Airport not found",
                            "value": {"detail": "Airport not found"},
                        },
                        "aircraft_not_found": {
                            "summary": "Aircraft not found",
                            "value": {"detail": "Aircraft not found"},
                        },
                    },
                },
            },
        },
        422: {
            "description": (
                "Invalid request body or departure and arrival "
                "resolve to the same airport."
            ),
        },
    },
)
def record_flight(
    request: Annotated[
        FlightLogCreate,
        Body(description="Details of the flight to add to the flight log."),
    ],
    db: Annotated[Session, Depends(get_db)],
    catalog: Annotated[
        AirportCatalog,
        Depends(get_airport_catalog),
    ],
):
    """Validate and save one simulator flight to the flight log.

    Args:
        request: Departure, arrival, aircraft, and optional rating.
        db: Database session supplied by FastAPI.
        catalog: Airport catalog supplied by FastAPI.

    Returns:
        FlightLogResponse: The newly persisted flight log record.

    Raises:
        HTTPException: 404 for unknown airport/aircraft, or 422 for
            identical departure and arrival airports.
    """
    dep = catalog.get_by_code(
        request.departure_icao,
    )

    arr = catalog.get_by_code(
        request.arrival_icao,
    )

    if not dep or not arr:
        raise HTTPException(
            status_code=404,
            detail="Airport not found",
        )

    if dep.icao_code == arr.icao_code:
        raise HTTPException(
            status_code=422,
            detail="Departure and arrival must differ",
        )

    if db.get(Aircraft, request.aircraft_id) is None:
        raise HTTPException(
            status_code=404,
            detail="Aircraft not found",
        )

    flight_log = FlightLog(
        departure_icao=dep.icao_code,
        arrival_icao=arr.icao_code,
        aircraft_id=request.aircraft_id,
        rating=request.rating,
    )

    db.add(flight_log)
    db.commit()
    db.refresh(flight_log)

    logger.info(
        "FLIGHT LOG | id=%s | %s -> %s | "
        "aircraft_id=%s | rating=%s",
        flight_log.id,
        flight_log.departure_icao,
        flight_log.arrival_icao,
        flight_log.aircraft_id,
        flight_log.rating,
    )

    return {
        "id": flight_log.id,
        "departure_icao": flight_log.departure_icao,
        "arrival_icao": flight_log.arrival_icao,
        "aircraft_id": flight_log.aircraft_id,
        "rating": flight_log.rating,
    }




class ExplicitValidationRequest(BaseModel):
    """Parameters for validating an aircraft against a proposed route."""

    aircraft_id: int = Field(
        ...,
        gt=0,
        description="Unique database ID of the aircraft to validate.",
        examples=[1],
    )

    departure_code: str = Field(
        ...,
        min_length=3,
        max_length=8,
        description="Code identifying the departure airport.",
        examples=["YBBN"],
    )

    arrival_code: str = Field(
        ...,
        min_length=3,
        max_length=8,
        description="Code identifying the arrival airport.",
        examples=["YSSY"],
    )

    route_distance_nm: float | None = Field(
        default=None,
        gt=0,
        description=(
            "Optional route distance in nautical miles. When omitted, "
            "the endpoint calculates a great-circle distance from "
            "airport coordinates."
        ),
        examples=[405.0],
    )

    require_paved: bool = Field(
        default=True,
        description=(
            "Whether the validation engine should require paved "
            "runway surfaces."
        ),
    )


class ExplicitValidationResponse(BaseModel):
    """Aircraft, airport, and g ate validation result for a proposed flight."""

    aircraft_id: int = Field(
        ...,
        description="Database identifier of the evaluated aircraft.",
        examples=[1],
    )

    aircraft_name: str = Field(
        ...,
        description="Display name of the evaluated aircraft.",
        examples=["Airbus A380-800"],
    )

    departure_icao: str = Field(
        ...,
        description="Resolved departure airport ICAO identifier.",
        examples=["YBBN"],
    )

    arrival_icao: str = Field(
        ...,
        description="Resolved arrival airport ICAO identifier.",
        examples=["YSSY"],
    )

    route_distance_nm: float = Field(
        ...,
        description="Distance used for evaluation, in nautical miles.",
        examples=[405.0],
    )

    distance_source: Literal["user_provided", "great_circle"] = Field(
        ...,
        description=(
            "Whether the distance came from the supplied request or "
            "was calculated from airport coordinates."
        ),
    )

    validation: dict[str, Any] = Field(
        ...,
        description=(
            "Detailed results of ValidationEngine.evaluate(), serialized "
            "using the validation assessment's to_dict() method."
        ),
    )

    departure_gate: dict[str, Any] = Field(
        ...,
        description=(
            "Departure gate suggestion returned by AirportEngine, "
            "serialized using GateSuggestion.to_dict()."
        ),
    )

    disclaimer: str = Field(
        ...,
        description="Reminder that this is simulator-only screening.",
    )

@router.post(
    "/validate",
    response_model=ExplicitValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate Aircraft and Airports",
    description=(
        "Evaluates a selected aircraft against a proposed flight "
        "between two airports.\n\n"
        "**Validation process:**\n"
        "1. Loads the aircraft and resolves both airports.\n"
        "2. Rejects requests where departure and arrival are the same airport.\n"
        "3. Uses the supplied route distance, or calculates great-circle "
        "distance when none is supplied.\n"
        "4. Runs the aircraft and airport validation engine, passing "
        "the `require_paved` option.\n"
        "5. Obtains a departure-gate suggestion from AirportEngine.\n"
        "6. Returns the validation, gate result, and distance source.\n\n"
        "**Important:** This is simulator-only screening, not a "
        "real-world aircraft performance or dispatch assessment."
    ),
    response_description=(
        "Validation details, flight distance information, "
        "and a departure-gate result."
    ),
    responses={
        404: {
            "description": "Requested aircraft or airport not found.",
            "content": {
                "application/json": {
                    "examples": {
                        "aircraft_not_found": {
                            "summary": "Aircraft not found",
                            "value": {"detail": "Aircraft not found"},
                        },
                        "airport_not_found": {
                            "summary": "Airport not found",
                            "value": {"detail": "Airport not found"},
                        },
                    },
                },
            },
        },
        422: {
            "description": (
                "Invalid request parameters or departure and arrival "
                "resolve to the same airport."
            ),
        },
    },
)
def validate_aircraft_and_airports(
    request: Annotated[
        ExplicitValidationRequest,
        Body(description="Aircraft, airport, and distance validation options."),
    ],
    db: Annotated[Session, Depends(get_db)],
    catalog: Annotated[
        AirportCatalog,
        Depends(get_airport_catalog),
    ],
):
    """Validate a proposed flight and return a departure-gate result.

    Args:
        request: Aircraft, airports, optional route distance, and paving flag.
        db: Database session supplied by FastAPI.
        catalog: Airport catalog supplied by FastAPI.

    Returns:
        ExplicitValidationResponse: Route validation and gate information.

    Raises:
        HTTPException: 404 for missing aircraft/airport, or 422 when
            departure and arrival refer to the same airport.
    """
    aircraft = db.get(
        Aircraft,
        request.aircraft_id,
    )

    departure = catalog.get_by_code(
        request.departure_code,
    )

    arrival = catalog.get_by_code(
        request.arrival_code,
    )

    if aircraft is None:
        raise HTTPException(
            status_code=404,
            detail="Aircraft not found",
        )

    if departure is None or arrival is None:
        raise HTTPException(
            status_code=404,
            detail="Airport not found",
        )

    if departure.icao_code == arrival.icao_code:
        raise HTTPException(
            status_code=422,
            detail="Departure and arrival must differ",
        )

    distance = (
        request.route_distance_nm
        or GeographicEngine.distance_nm(
            departure.latitude,
            departure.longitude,
            arrival.latitude,
            arrival.longitude,
        )
    )

    logger.info(
        "VALIDATE | %s -> %s | aircraft=%s | "
        "distance_nm=%.2f | require_paved=%s",
        departure.icao_code,
        arrival.icao_code,
        aircraft.display_name,
        distance,
        request.require_paved,
    )

    airport_engine = AirportEngine(
    gate_inventory_path=(
        os.getenv("MSFS_GATE_INVENTORY") or None
    ),
)

    assessment = airport_engine.validate_route(
        aircraft=aircraft,
        departure=departure,
        arrival=arrival,
        distance_nm=distance,
        require_paved=request.require_paved,
    )

    assessment_data = assessment.to_dict()

    logger.info(
        "VALIDATION RESULT | %s -> %s | "
        "aircraft=%s | status=%s",
        departure.icao_code,
        arrival.icao_code,
        aircraft.display_name,
        assessment_data.get("status", "unknown"),
    )

    for issue in assessment_data.get("issues", []):
        logger.info(
            "VALIDATION ISSUE | %s -> %s | "
            "code=%s | reason=%s",
            departure.icao_code,
            arrival.icao_code,
            issue.get("code", "unknown"),
            issue.get("message", "No reason supplied"),
        )

    gates = AirportEngine(
        gate_inventory_path=(
            os.getenv("MSFS_GATE_INVENTORY") or None
        )
    )

    return {
        "aircraft_id": aircraft.id,
        "aircraft_name": aircraft.display_name,
        "departure_icao": departure.icao_code,
        "arrival_icao": arrival.icao_code,
        "route_distance_nm": round(distance, 2),
        "distance_source": (
            "user_provided"
            if request.route_distance_nm
            else "great_circle"
        ),
        "validation": assessment_data,
        "departure_gate": airport_engine.suggest_gate(
            airport_icao=departure.icao_code,
            aircraft=aircraft,
        ).to_dict(),
        "disclaimer": (
            "Simulator-only screening; not a real-world "
            "performance or dispatch assessment"
        ),
    }
