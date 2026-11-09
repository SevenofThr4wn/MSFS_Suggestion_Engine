from __future__ import annotations


from app.ml.reliability import assess_prediction_reliability

import os
from functools import lru_cache
from pathlib import Path

import joblib

from app.core.logging import get_logger
from app.ml.features import prediction_features
from app.schemas.ml import (
    AircraftPredictionCandidate,
    AircraftPredictionRequest,
    AircraftPredictionResponse,
    MLModelStatus,
)


logger = get_logger("ml.predictor")


def model_path() -> Path:
    """Locate the configured model artifact."""
    configured = os.getenv(
        "FLIGHTENGINE_ML_MODEL_PATH",
        "models/aircraft_assignment.joblib",
    )

    return Path(configured).expanduser().resolve()


@lru_cache(maxsize=1)
def load_model() -> dict:
    """Load the locally trained model on first use."""
    path = model_path()

    if not path.is_file():
        raise FileNotFoundError(
            f"ML model not found: {path}"
        )

    # joblib uses pickle. Only load artifacts created
    # by FlightEngine or from a trusted source.
    artifact = joblib.load(path)

    required = {
        "version",
        "model",
        "classes",
        "trained_rows",
    }

    if not isinstance(artifact, dict):
        raise ValueError("Invalid ML model artifact.")

    if not required.issubset(artifact):
        raise ValueError(
            "ML model artifact is missing required metadata."
        )

    logger.info(
        "ML MODEL LOADED | version=%s | rows=%s | path=%s",
        artifact["version"],
        artifact["trained_rows"],
        path,
    )

    return artifact


def get_model_status() -> MLModelStatus:
    """Return availability and metadata for the trained model."""
    if not model_path().is_file():
        return MLModelStatus(
            available=False,
            message="No aircraft assignment model has been trained.",
        )

    artifact = load_model()

    return MLModelStatus(
        available=True,
        model_version=str(artifact["version"]),
        trained_rows=int(artifact["trained_rows"]),
        classes=list(artifact["classes"]),
    )


def predict_aircraft(
    request: AircraftPredictionRequest,
) -> AircraftPredictionResponse:
    """Predict likely aircraft types for an airline-route pair."""
    artifact = load_model()

    features = prediction_features(request)
    pipeline = artifact["model"]

    probabilities = pipeline.predict_proba(features)[0]

    classes = pipeline.named_steps[
        "classifier"
    ].classes_

    candidates = sorted(
        (
            AircraftPredictionCandidate(
                aircraft_icao=str(aircraft),
                model_score=round(float(score), 4),
            )
            for aircraft, score in zip(
                classes,
                probabilities,
            )
        ),
        key=lambda candidate: candidate.model_score,
        reverse=True,
    )

    highest_score = candidates[0].model_score

    second_score = (
        candidates[1].model_score
        if len(candidates) > 1
        else 0.0
    )

    reliability, reliability_warnings = (
        assess_prediction_reliability(
            request=request,
            artifact=artifact,
            highest_score=highest_score,
            second_score=second_score,
        )
    )

    logger.info(
        "ML RELIABILITY | %s -> %s | "
        "airline=%s | reliability=%s | warnings=%d",
        request.departure_icao,
        request.arrival_icao,
        request.airline_icao,
        reliability,
        len(reliability_warnings),
    )

    logger.info(
        "ML PREDICTION | %s -> %s | airline=%s | "
        "prediction=%s | score=%.4f",
        request.departure_icao,
        request.arrival_icao,
        request.airline_icao,
        candidates[0].aircraft_icao,
        candidates[0].model_score,
    )

    return AircraftPredictionResponse(
    predicted_aircraft_icao=candidates[0].aircraft_icao,
    model_version=str(artifact["version"]),
    candidates=candidates[:5],
    reliability=reliability,
    reliability_warnings=reliability_warnings,
)
