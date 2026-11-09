
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from app.core.logging import get_logger
from app.ml.features import prediction_features
from app.ml.reliability import assess_prediction_reliability
from app.schemas.ml import (
    AircraftPredictionCandidate,
    AircraftPredictionRequest,
    AircraftPredictionResponse,
    MLModelStatus,
)


logger = get_logger("ml.predictor")

# ============================================================
# Configuration
# ============================================================

MODEL_ENV_VAR = "FLIGHTENGINE_ML_MODEL_PATH"

DEFAULT_MODEL_PATH = (
    "models/v2/aircraft_assignment.joblib"
)

MAX_CANDIDATES = 5

REQUIRED_METADATA = frozenset({
    "version",
    "model",
    "classes",
    "trained_rows",
})


# ============================================================
# Model Loading
# ============================================================

def model_path() -> Path:
    """Resolve the configured aircraft prediction model."""

    configured = os.getenv(
        MODEL_ENV_VAR,
        DEFAULT_MODEL_PATH,
    )

    return Path(configured).expanduser().resolve()


def validate_model_artifact(
    artifact: Any,
) -> dict:
    """
    Validate a loaded aircraft prediction artifact.

    Ensures the artifact contains the metadata and
    fitted estimator methods required for inference.
    """

    if not isinstance(artifact, dict):
        raise ValueError(
            "Invalid ML artifact: expected a dictionary."
        )

    missing = REQUIRED_METADATA - artifact.keys()

    if missing:
        raise ValueError(
            "Aircraft ML artifact is missing required "
            f"metadata: {sorted(missing)}"
        )

    model = artifact["model"]

    if not callable(
        getattr(model, "predict_proba", None)
    ):
        raise ValueError(
            "Aircraft ML model does not support "
            "probability prediction."
        )

    if not hasattr(model, "named_steps"):
        raise ValueError(
            "Aircraft ML model must be a fitted pipeline."
        )

    classifier = model.named_steps.get("classifier")

    if classifier is None:
        raise ValueError(
            "Aircraft ML pipeline has no classifier step."
        )

    classes = getattr(classifier, "classes_", None)

    if classes is None or len(classes) == 0:
        raise ValueError(
            "Aircraft ML classifier has no fitted classes."
        )

    expected_classes = {
        str(value)
        for value in artifact["classes"]
    }

    actual_classes = {
        str(value)
        for value in classes
    }

    if expected_classes != actual_classes:
        raise ValueError(
            "Stored aircraft classes do not match "
            "the fitted classifier."
        )

    if int(artifact["trained_rows"]) <= 0:
        raise ValueError(
            "Aircraft ML artifact contains no training rows."
        )

    if not artifact.get("version"):
        raise ValueError(
            "Aircraft ML artifact has no model version."
        )

    return artifact


@lru_cache(maxsize=1)
def load_model() -> dict:
    """
    Load and cache the aircraft prediction model.

    Only trusted locally generated joblib artifacts
    should be loaded.
    """

    path = model_path()

    if not path.is_file():
        raise FileNotFoundError(
            f"Aircraft ML model not found: {path}"
        )

    try:
        artifact = joblib.load(path)

        artifact = validate_model_artifact(
            artifact
        )

    except Exception:
        logger.exception(
            "AIRCRAFT ML LOAD FAILED | path=%s",
            path,
        )
        raise

    logger.info(
        "AIRCRAFT ML LOADED | version=%s | "
        "rows=%d | classes=%d | path=%s",
        artifact["version"],
        int(artifact["trained_rows"]),
        len(artifact["classes"]),
        path,
    )

    return artifact


def clear_model_cache() -> None:
    """
    Clear the cached aircraft model.

    Useful after retraining or replacing a model
    artifact without restarting the Python process.
    """

    load_model.cache_clear()

    logger.info(
        "AIRCRAFT ML CACHE CLEARED"
    )


# ============================================================
# Model Status
# ============================================================

def get_model_status() -> MLModelStatus:
    """
    Return aircraft model availability and metadata.

    Does not perform predictions.
    """

    path = model_path()

    if not path.is_file():
        return MLModelStatus(
            available=False,
            message=(
                "Aircraft prediction model has "
                "not been trained or is missing."
            ),
        )

    artifact = load_model()

    return MLModelStatus(
        available=True,
        model_version=str(
            artifact["version"]
        ),
        trained_rows=int(
            artifact["trained_rows"]
        ),
        classes=sorted(
            str(value)
            for value in artifact["classes"]
        ),
        message=(
            "Aircraft prediction model is available."
        ),
    )


# ============================================================
# Prediction Utilities
# ============================================================

def get_aircraft_probabilities(
    request: AircraftPredictionRequest,
    artifact: dict,
) -> list[tuple[str, float]]:
    """
    Return the full aircraft prediction distribution.

    Scores are model outputs and must not be treated
    as calibrated probabilities of actual operation.
    """

    features = prediction_features(request)

    pipeline = artifact["model"]

    probabilities = np.asarray(
        pipeline.predict_proba(features),
        dtype=float,
    )

    classes = pipeline.named_steps[
        "classifier"
    ].classes_

    if probabilities.shape != (1, len(classes)):
        raise ValueError(
            "Aircraft classifier returned an "
            "unexpected prediction shape."
        )

    scores = probabilities[0]

    if not np.isfinite(scores).all():
        raise ValueError(
            "Aircraft classifier returned "
            "non-finite prediction scores."
        )

    if (scores < 0).any():
        raise ValueError(
            "Aircraft classifier returned "
            "negative prediction scores."
        )

    total = float(scores.sum())

    if total <= 0:
        raise ValueError(
            "Aircraft classifier returned "
            "no usable prediction scores."
        )

    if not np.isclose(total, 1.0, atol=1e-5):
        raise ValueError(
            "Aircraft classifier probabilities "
            "do not sum to one."
        )

    predictions = [
        (
            str(aircraft),
            float(score),
        )
        for aircraft, score in zip(classes, scores)
    ]

    return sorted(
        predictions,
        key=lambda item: (-item[1], item[0]),
    )


# ============================================================
# Aircraft Prediction
# ============================================================

def predict_aircraft(
    request: AircraftPredictionRequest,
) -> AircraftPredictionResponse:
    """
    Predict likely aircraft types for an airline-route pair.

    Returns the leading aircraft and a ranked shortlist.

    These results represent statistical predictions,
    not verified airline equipment assignments.
    """

    artifact = load_model()

    predictions = get_aircraft_probabilities(
        request=request,
        artifact=artifact,
    )

    if not predictions:
        raise ValueError(
            "Aircraft model returned no candidates."
        )

    top_aircraft, highest_score = predictions[0]

    second_score = (
        predictions[1][1]
        if len(predictions) > 1
        else 0.0
    )

    # Use unrounded model scores when assessing reliability.
    reliability, reliability_warnings = (
        assess_prediction_reliability(
            request=request,
            artifact=artifact,
            highest_score=highest_score,
            second_score=second_score,
        )
    )

    candidates = [
        AircraftPredictionCandidate(
            aircraft_icao=aircraft,
            model_score=round(score, 4),
        )
        for aircraft, score in predictions[:MAX_CANDIDATES]
    ]

    logger.info(
        "AIRCRAFT ML PREDICTION | "
        "%s -> %s | airline=%s | "
        "aircraft=%s | score=%.4f | "
        "reliability=%s | version=%s",
        request.departure_icao,
        request.arrival_icao,
        request.airline_icao,
        top_aircraft,
        highest_score,
        reliability,
        artifact["version"],
    )

    if reliability_warnings:
        logger.debug(
            "AIRCRAFT ML WARNINGS | %s",
            reliability_warnings,
        )

    return AircraftPredictionResponse(
        predicted_aircraft_icao=top_aircraft,
        model_version=str(artifact["version"]),
        candidates=candidates,
        reliability=reliability,
        reliability_warnings=reliability_warnings,
        verified_assignment=False,
    )
