
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import joblib

from app.core.logging import get_logger
from app.ml.features import prediction_features
from app.ml.reliability import assess_prediction_reliability
from app.schemas.ml import (
    AircraftFamilyCandidate,
    AircraftFamilyPredictionResponse,
    AircraftPredictionRequest,
)


logger = get_logger("ml.family_predictor")


def family_model_path() -> Path:
    configured = os.getenv(
        "FLIGHTENGINE_ML_FAMILY_MODEL_PATH",
        "models/aircraft_family.joblib",
    )
    return Path(configured).expanduser().resolve()


@lru_cache(maxsize=1)
def load_family_model() -> dict:
    path = family_model_path()

    if not path.is_file():
        raise FileNotFoundError(
            f"Aircraft-family model not found: {path}"
        )

    # Only load model artifacts created by trusted code.
    artifact = joblib.load(path)

    if not isinstance(artifact, dict) or not {
        "model", "version", "family_names",
        "known_airlines", "known_airports",
    }.issubset(artifact):
        raise ValueError(
            "Invalid aircraft-family model artifact."
        )

    logger.info(
        "FAMILY MODEL LOADED | version=%s | path=%s",
        artifact["version"],
        path,
    )

    return artifact


def predict_aircraft_family(
    request: AircraftPredictionRequest,
) -> AircraftFamilyPredictionResponse:
    artifact = load_family_model()
    pipeline = artifact["model"]

    features = prediction_features(request)
    scores = pipeline.predict_proba(features)[0]
    classes = pipeline.named_steps["classifier"].classes_

    candidates = sorted(
        [
            AircraftFamilyCandidate(
                family_id=str(family_id),
                family_name=artifact["family_names"].get(
                    str(family_id),
                    str(family_id),
                ),
                model_score=round(float(score), 4),
            )
            for family_id, score in zip(classes, scores)
        ],
        key=lambda candidate: candidate.model_score,
        reverse=True,
    )

    if not candidates:
        raise ValueError(
            "Aircraft-family model returned no candidates."
        )

    highest = candidates[0].model_score
    second = (
        candidates[1].model_score
        if len(candidates) > 1
        else 0.0
    )

    reliability, warnings = assess_prediction_reliability(
        request=request,
        artifact=artifact,
        highest_score=highest,
        second_score=second,
    )

    logger.info(
        "FAMILY PREDICTION | %s -> %s | "
        "airline=%s | family=%s | score=%.4f | reliability=%s",
        request.departure_icao,
        request.arrival_icao,
        request.airline_icao,
        candidates[0].family_id,
        highest,
        reliability,
    )

    return AircraftFamilyPredictionResponse(
        predicted_family_id=candidates[0].family_id,
        predicted_family_name=candidates[0].family_name,
        model_version=str(artifact["version"]),
        candidates=candidates[:5],
        reliability=reliability,
        reliability_warnings=warnings,
    )
