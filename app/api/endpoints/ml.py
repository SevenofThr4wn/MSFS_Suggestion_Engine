
from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.logging import get_logger

from app.ml.predictor import (
    get_model_status,
    load_model,
    predict_aircraft,
)

from app.ml.family_predictor import (
    load_family_model,
    predict_aircraft_family,
)

from app.ml.hybrid_predictor import (
    predict_hybrid_aircraft,
)

from app.schemas.ml import (
    AircraftFamilyPredictionResponse,
    AircraftPredictionRequest,
    AircraftPredictionResponse,
    HybridAircraftPredictionResponse,
    MLModelStatus,
)


# ============================================================
# Router Configuration
# ============================================================

router = APIRouter(
    prefix="/ml",
    tags=["Machine Learning"],
)

logger = get_logger("api.ml")

T = TypeVar("T")


# ============================================================
# Status Schemas
# ============================================================

class ModelReadiness(BaseModel):
    """Availability and metadata for one trained model."""

    available: bool

    model_version: str | None = None

    trained_rows: int | None = None

    classes: int | None = None

    message: str | None = None


class HybridReadiness(BaseModel):
    """Availability of the combined prediction service."""

    available: bool

    complete: bool

    message: str


class MLModelsStatus(BaseModel):
    """Status of all FlightEngine ML components."""

    aircraft: ModelReadiness

    family: ModelReadiness

    hybrid: HybridReadiness

    ready_models: int = Field(
        ge=0,
        le=2,
    )


# ============================================================
# Shared Error Handling
# ============================================================

def execute_prediction(
    request: AircraftPredictionRequest,
    predictor: Callable[[AircraftPredictionRequest], T],
    service_name: str,
) -> T:
    """
    Execute an ML prediction with consistent error handling.

    Expected validation errors are handled by FastAPI and
    Pydantic before the endpoint calls this function.

    Missing, damaged or incompatible model artifacts
    produce HTTP 503 rather than exposing internal errors.
    """

    try:
        result = predictor(request)

        logger.info(
            "ML API SUCCESS | service=%s | "
            "airline=%s | %s -> %s",
            service_name,
            request.airline_icao,
            request.departure_icao,
            request.arrival_icao,
        )

        return result

    except FileNotFoundError as exc:
        logger.warning(
            "ML API UNAVAILABLE | service=%s | "
            "airline=%s | %s -> %s",
            service_name,
            request.airline_icao,
            request.departure_icao,
            request.arrival_icao,
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"{service_name} model is unavailable. "
                "Check that the required model artifacts "
                "have been trained and configured."
            ),
        ) from exc

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception(
            "ML API FAILED | service=%s | "
            "airline=%s | %s -> %s",
            service_name,
            request.airline_icao,
            request.departure_icao,
            request.arrival_icao,
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"{service_name} prediction service "
                "is currently unavailable."
            ),
        ) from exc


# ============================================================
# Model Readiness
# ============================================================

def inspect_model(
    loader: Callable[[], dict[str, Any]],
    name: str,
) -> ModelReadiness:
    """
    Inspect a model without performing inference.

    The loader validates the artifact and uses its
    existing cache when previously loaded.

    Failure of one model must not prevent inspection
    of the other.
    """

    try:
        artifact = loader()

        return ModelReadiness(
            available=True,
            model_version=str(
                artifact["version"]
            ),
            trained_rows=int(
                artifact["trained_rows"]
            ),
            classes=len(
                artifact["classes"]
            ),
            message=f"{name} model is ready.",
        )

    except FileNotFoundError:
        return ModelReadiness(
            available=False,
            message=f"{name} model was not found.",
        )

    except Exception:
        logger.exception(
            "ML MODEL INSPECTION FAILED | model=%s",
            name,
        )

        return ModelReadiness(
            available=False,
            message=(
                f"{name} model could not be loaded."
            ),
        )


# ============================================================
# Existing Model Status Endpoint
# ============================================================

@router.get(
    "/status",
    response_model=MLModelStatus,
    summary="Get aircraft prediction model status",
    description=(
        "Return availability and metadata for the "
        "aircraft-type prediction model. "
        "This endpoint is retained for compatibility "
        "with existing FlightEngine clients."
    ),
    responses={
        503: {
            "description": (
                "Aircraft model could not be inspected."
            ),
        },
    },
)
def ml_status() -> MLModelStatus:
    """Return aircraft-type model availability."""

    try:
        return get_model_status()

    except Exception as exc:
        logger.exception(
            "ML STATUS FAILED"
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Aircraft model status is unavailable."
            ),
        ) from exc


# ============================================================
# Combined ML Status Endpoint
# ============================================================

@router.get(
    "/status/models",
    response_model=MLModelsStatus,
    summary="Get all ML model statuses",
    description=(
        "Inspect aircraft-type, aircraft-family, "
        "and hybrid prediction readiness. "
        "Hybrid prediction supports degraded operation "
        "when only one model is available."
    ),
)
def ml_models_status() -> MLModelsStatus:
    """Return readiness of all trained ML components."""

    aircraft = inspect_model(
        load_model,
        "Aircraft-type",
    )

    family = inspect_model(
        load_family_model,
        "Aircraft-family",
    )

    ready_models = int(
        aircraft.available
    ) + int(
        family.available
    )

    hybrid_available = ready_models >= 1
    hybrid_complete = ready_models == 2

    if hybrid_complete:
        hybrid_message = (
            "Both models are ready. "
            "Hybrid fusion is available."
        )

    elif hybrid_available:
        hybrid_message = (
            "One model is available. "
            "Hybrid predictions will operate "
            "without independent model agreement."
        )

    else:
        hybrid_message = (
            "No trained aircraft ML models are available."
        )

    logger.info(
        "ML MODELS STATUS | aircraft=%s | "
        "family=%s | hybrid=%s",
        aircraft.available,
        family.available,
        hybrid_complete,
    )

    return MLModelsStatus(
        aircraft=aircraft,
        family=family,
        hybrid=HybridReadiness(
            available=hybrid_available,
            complete=hybrid_complete,
            message=hybrid_message,
        ),
        ready_models=ready_models,
    )


# ============================================================
# Aircraft-Type Prediction
# ============================================================

@router.post(
    "/aircraft/predict",
    response_model=AircraftPredictionResponse,
    summary="Predict aircraft type",
    description=(
        "Predict likely ICAO aircraft types for an "
        "airline and route using the trained V2 aircraft "
        "classifier. Returns a ranked top-five shortlist "
        "and a heuristic reliability assessment. "
        "Predictions are not verified equipment assignments."
    ),
    responses={
        503: {
            "description": (
                "Aircraft prediction model is unavailable."
            ),
        },
    },
)
def aircraft_prediction(
    request: AircraftPredictionRequest,
) -> AircraftPredictionResponse:
    """Predict aircraft variants using the aircraft model."""

    return execute_prediction(
        request=request,
        predictor=predict_aircraft,
        service_name="Aircraft-type",
    )


# ============================================================
# Aircraft-Family Prediction
# ============================================================

@router.post(
    "/aircraft/family/predict",
    response_model=AircraftFamilyPredictionResponse,
    summary="Predict aircraft family",
    description=(
        "Predict likely aircraft families using the "
        "trained V2 family classifier. Returns a ranked "
        "family shortlist and heuristic reliability "
        "assessment. Predictions are statistical estimates."
    ),
    responses={
        503: {
            "description": (
                "Aircraft-family prediction model "
                "is unavailable."
            ),
        },
    },
)
def aircraft_family_prediction(
    request: AircraftPredictionRequest,
) -> AircraftFamilyPredictionResponse:
    """Predict the most likely aircraft families."""

    return execute_prediction(
        request=request,
        predictor=predict_aircraft_family,
        service_name="Aircraft-family",
    )


# ============================================================
# Hybrid Aircraft Prediction
# ============================================================

@router.post(
    "/aircraft/hybrid/predict",
    response_model=HybridAircraftPredictionResponse,
    summary="Predict aircraft using Hybrid ML V2",
    description=(
        "Combine the aircraft-type and aircraft-family "
        "classifiers to generate a fused aircraft shortlist. "
        "The hybrid system considers family compatibility, "
        "model agreement, and heuristic reliability. "
        "It may abstain from choosing a definitive aircraft "
        "while still returning ranked suggestions. "
        "If only one model is available, the service "
        "operates in a degraded mode."
    ),
    responses={
        503: {
            "description": (
                "No usable aircraft prediction "
                "models are available."
            ),
        },
    },
)
def hybrid_aircraft_prediction(
    request: AircraftPredictionRequest,
) -> HybridAircraftPredictionResponse:
    """Combine the two V2 classifiers conservatively."""

    return execute_prediction(
        request=request,
        predictor=predict_hybrid_aircraft,
        service_name="Hybrid aircraft",
    )
