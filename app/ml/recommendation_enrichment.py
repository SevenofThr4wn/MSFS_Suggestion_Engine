
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import ValidationError

from app.core.logging import get_logger
from app.ml.hybrid_predictor import predict_hybrid_aircraft
from app.schemas.ml import (
    AircraftPredictionRequest,
    HybridAircraftPredictionResponse,
)
from app.schemas.route import RouteRecommendation


logger = get_logger("ml.recommendation_enrichment")

MLStatus = Literal[
    "available",
    "disabled",
    "skipped",
    "unavailable",
]


@lru_cache(maxsize=512)
def _predict_cached(
    airline: str,
    departure: str,
    arrival: str,
    distance_nm: float,
) -> HybridAircraftPredictionResponse:
    """Reuse predictions for identical inputs."""

    request = AircraftPredictionRequest(
        airline_icao=airline,
        departure_icao=departure,
        arrival_icao=arrival,
        distance_nm=distance_nm,
    )

    return predict_hybrid_aircraft(request)


def clear_prediction_cache() -> None:
    """Clear cached route-level ML predictions."""

    _predict_cached.cache_clear()


def enrich_recommendation(
    route: RouteRecommendation,
) -> tuple[HybridAircraftPredictionResponse | None, MLStatus]:
    """
    Obtain aircraft suggestions for one validated route.

    Does not modify route aircraft, suitability,
    verification evidence, or recommendation scores.

    ML failure must not prevent normal recommendations.
    """

    if not route.airline_icao:
        return None, "skipped"

    if not (
        route.departure_icao
        and route.arrival_icao
        and 0 < route.distance_nm <= 20000
    ):
        return None, "skipped"

    airline = route.airline_icao.strip().upper()
    departure = route.departure_icao.strip().upper()
    arrival = route.arrival_icao.strip().upper()

    try:
        prediction = _predict_cached(
            airline,
            departure,
            arrival,
            round(float(route.distance_nm), 2),
        )

        return prediction, "available"

    except ValidationError as exc:
        logger.warning(
            "ML ENRICHMENT SKIPPED | %s -> %s | %s",
            departure,
            arrival,
            exc,
        )
        return None, "skipped"

    except FileNotFoundError:
        logger.warning(
            "ML ENRICHMENT UNAVAILABLE | model missing"
        )
        return None, "unavailable"

    except Exception:
        logger.exception(
            "ML ENRICHMENT FAILED | %s -> %s | airline=%s",
            departure,
            arrival,
            airline,
        )
        return None, "unavailable"
