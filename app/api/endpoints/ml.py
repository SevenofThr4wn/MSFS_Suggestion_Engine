from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.logging import get_logger
from app.ml.predictor import (
    get_model_status,
    predict_aircraft,
)
from app.schemas.ml import (
    AircraftPredictionRequest,
    AircraftPredictionResponse,
    MLModelStatus,
)

from app.ml.family_predictor import predict_aircraft_family
from app.schemas.ml import AircraftFamilyPredictionResponse

from app.ml.hybrid_predictor import predict_hybrid_aircraft
from app.schemas.ml import HybridAircraftPredictionResponse

router = APIRouter(
    prefix="/ml",
    tags=["Machine Learning"],
)

logger = get_logger("api.ml")


@router.get(
    "/status",
    response_model=MLModelStatus,
)
def ml_status() -> MLModelStatus:
    """Return aircraft prediction model availability."""
    try:
        return get_model_status()

    except Exception:
        logger.exception(
            "ML STATUS FAILED | Unable to inspect model"
        )

        raise HTTPException(
            status_code=503,
            detail="ML model is unavailable.",
        )


@router.post(
    "/aircraft/predict",
    response_model=AircraftPredictionResponse,
)
def aircraft_prediction(
    request: AircraftPredictionRequest,
) -> AircraftPredictionResponse:
    """Predict likely aircraft types using a trained model."""
    try:
        return predict_aircraft(request)

    except FileNotFoundError as exc:
        logger.warning(
            "ML PREDICTION UNAVAILABLE | Model not trained"
        )

        raise HTTPException(
            status_code=503,
            detail="Aircraft prediction model has not been trained.",
        ) from exc

    except Exception as exc:
        logger.exception(
            "ML PREDICTION FAILED | %s -> %s",
            request.departure_icao,
            request.arrival_icao,
        )

        raise HTTPException(
            status_code=503,
            detail="Aircraft prediction service is unavailable.",
        ) from exc

@router.post(
    "/aircraft/family/predict",
    response_model=AircraftFamilyPredictionResponse,
)
def aircraft_family_prediction(
    request: AircraftPredictionRequest,
) -> AircraftFamilyPredictionResponse:
    """Predict an aircraft family from historical route data."""
    try:
        return predict_aircraft_family(request)

    except FileNotFoundError as exc:
        logger.warning(
            "FAMILY PREDICTION UNAVAILABLE | Model not trained"
        )
        raise HTTPException(
            status_code=503,
            detail="Aircraft-family model has not been trained.",
        ) from exc

    except Exception as exc:
        logger.exception(
            "FAMILY PREDICTION FAILED | %s -> %s",
            request.departure_icao,
            request.arrival_icao,
        )
        raise HTTPException(
            status_code=503,
            detail="Aircraft-family prediction is unavailable.",
        ) from exc

@router.post(
    "/aircraft/hybrid/predict",
    response_model=HybridAircraftPredictionResponse,
    summary="Predict aircraft using both ML models",
)
def hybrid_aircraft_prediction(
    request: AircraftPredictionRequest,
) -> HybridAircraftPredictionResponse:
    """Combine variant and aircraft-family predictions."""
    try:
        return predict_hybrid_aircraft(request)

    except FileNotFoundError as exc:
        logger.warning(
            "HYBRID ML UNAVAILABLE | %s -> %s",
            request.departure_icao,
            request.arrival_icao,
        )

        raise HTTPException(
            status_code=503,
            detail="No trained aircraft ML models are available.",
        ) from exc

    except Exception as exc:
        logger.exception(
            "HYBRID ML FAILED | %s -> %s | airline=%s",
            request.departure_icao,
            request.arrival_icao,
            request.airline_icao,
        )

        raise HTTPException(
            status_code=503,
            detail="Hybrid aircraft prediction is unavailable.",
        ) from exc