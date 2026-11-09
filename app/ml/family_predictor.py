
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
    AircraftFamilyCandidate,
    AircraftFamilyPredictionResponse,
    AircraftPredictionRequest,
)


logger = get_logger("ml.family_predictor")


# ============================================================
# Configuration
# ============================================================

MODEL_ENV_VAR = "FLIGHTENGINE_ML_FAMILY_MODEL_PATH"

DEFAULT_MODEL_PATH = "models/v2/aircraft_family.joblib"

MAX_CANDIDATES = 5

REQUIRED_METADATA = frozenset({
    "version",
    "model",
    "classes",
    "trained_rows",
    "family_names",
    "known_airlines",
    "known_airports",
})


# ============================================================
# Model Loading
# ============================================================

def family_model_path() -> Path:
    """
    Resolve the configured aircraft-family model path.

    Environment variable:
        FLIGHTENGINE_ML_FAMILY_MODEL_PATH
    """

    configured = os.getenv(
        MODEL_ENV_VAR,
        DEFAULT_MODEL_PATH,
    )

    return Path(configured).expanduser().resolve()


def validate_family_artifact(
    artifact: Any,
) -> dict:
    """
    Validate the structure of a trained family model.

    Verifies required metadata and ensures the fitted
    classifier is compatible with prediction requests.
    """

    if not isinstance(artifact, dict):
        raise ValueError(
            "Invalid aircraft-family artifact: "
            "expected a dictionary."
        )

    missing = REQUIRED_METADATA - artifact.keys()

    if missing:
        raise ValueError(
            "Aircraft-family artifact is missing "
            f"required metadata: {sorted(missing)}"
        )

    if not artifact["version"]:
        raise ValueError(
            "Aircraft-family artifact has no version."
        )

    if int(artifact["trained_rows"]) <= 0:
        raise ValueError(
            "Aircraft-family artifact contains "
            "no training records."
        )

    model = artifact["model"]

    if not callable(
        getattr(model, "predict_proba", None)
    ):
        raise ValueError(
            "Aircraft-family model does not "
            "support probability prediction."
        )

    if not hasattr(model, "named_steps"):
        raise ValueError(
            "Aircraft-family model must be "
            "a fitted sklearn pipeline."
        )

    classifier = model.named_steps.get("classifier")

    if classifier is None:
        raise ValueError(
            "Aircraft-family pipeline is missing "
            "the classifier step."
        )

    classes = getattr(
        classifier,
        "classes_",
        None,
    )

    if classes is None or len(classes) == 0:
        raise ValueError(
            "Aircraft-family classifier "
            "has no fitted classes."
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
            "Stored family classes do not match "
            "the fitted classifier classes."
        )

    family_names = artifact["family_names"]

    if not isinstance(family_names, dict):
        raise ValueError(
            "Aircraft-family names must be a dictionary."
        )

    missing_names = actual_classes - set(family_names)

    if missing_names:
        raise ValueError(
            "Missing aircraft-family display names: "
            f"{sorted(missing_names)}"
        )

    for field in ("known_airlines", "known_airports"):
        values = artifact[field]

        if not isinstance(values, (list, tuple, set)):
            raise ValueError(
                f"Invalid training coverage metadata: {field}"
            )

    return artifact


@lru_cache(maxsize=1)
def load_family_model() -> dict:
    """
    Load and cache the trained aircraft-family model.

    Only trusted local joblib artifacts should be loaded.
    """

    path = family_model_path()

    if not path.is_file():
        raise FileNotFoundError(
            f"Aircraft-family ML model not found: {path}"
        )

    try:
        artifact = joblib.load(path)

        artifact = validate_family_artifact(
            artifact
        )

    except Exception:
        logger.exception(
            "FAMILY ML LOAD FAILED | path=%s",
            path,
        )
        raise

    logger.info(
        "FAMILY ML LOADED | version=%s | "
        "rows=%d | families=%d | path=%s",
        artifact["version"],
        int(artifact["trained_rows"]),
        len(artifact["classes"]),
        path,
    )

    return artifact


def clear_family_model_cache() -> None:
    """
    Clear the cached aircraft-family model.

    Useful after retraining or replacing model artifacts
    without restarting the application.
    """

    load_family_model.cache_clear()

    logger.info(
        "FAMILY ML CACHE CLEARED"
    )


# ============================================================
# Prediction Utilities
# ============================================================

def get_family_probabilities(
    request: AircraftPredictionRequest,
    artifact: dict,
) -> list[tuple[str, float]]:
    """
    Return the full ranked aircraft-family distribution.

    Scores are uncalibrated classifier outputs, not
    verified probabilities of actual airline operations.
    """

    features = prediction_features(request)

    model = artifact["model"]

    probabilities = np.asarray(
        model.predict_proba(features),
        dtype=float,
    )

    classes = model.named_steps[
        "classifier"
    ].classes_

    if probabilities.shape != (1, len(classes)):
        raise ValueError(
            "Aircraft-family classifier returned "
            "an unexpected prediction shape."
        )

    scores = probabilities[0]

    if not np.isfinite(scores).all():
        raise ValueError(
            "Aircraft-family classifier returned "
            "non-finite prediction scores."
        )

    if (scores < 0).any():
        raise ValueError(
            "Aircraft-family classifier returned "
            "negative prediction scores."
        )

    total = float(scores.sum())

    if total <= 0:
        raise ValueError(
            "Aircraft-family classifier returned "
            "no usable prediction scores."
        )

    if not np.isclose(total, 1.0, atol=1e-5):
        raise ValueError(
            "Aircraft-family prediction scores "
            "do not sum to one."
        )

    predictions = [
        (
            str(family_id),
            float(score),
        )
        for family_id, score in zip(classes, scores)
    ]

    return sorted(
        predictions,
        key=lambda item: (-item[1], item[0]),
    )


# ============================================================
# Family Prediction
# ============================================================

def predict_aircraft_family(
    request: AircraftPredictionRequest,
) -> AircraftFamilyPredictionResponse:
    """
    Predict likely aircraft families for an airline route.

    Returns:
        - Leading aircraft family
        - Ranked family candidates
        - Model version
        - Reliability assessment
        - Relevant warnings

    These predictions do not establish current airline
    operations or verified aircraft assignments.
    """

    artifact = load_family_model()

    predictions = get_family_probabilities(
        request=request,
        artifact=artifact,
    )

    if not predictions:
        raise ValueError(
            "Aircraft-family model returned no candidates."
        )

    family_id, highest_score = predictions[0]

    second_score = (
        predictions[1][1]
        if len(predictions) > 1
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

    family_names = artifact["family_names"]

    candidates = [
        AircraftFamilyCandidate(
            family_id=candidate_id,
            family_name=family_names.get(
                candidate_id,
                candidate_id,
            ),
            model_score=round(score, 4),
        )
        for candidate_id, score in predictions[:MAX_CANDIDATES]
    ]

    logger.info(
        "FAMILY ML PREDICTION | "
        "%s -> %s | airline=%s | "
        "family=%s | score=%.4f | "
        "reliability=%s | version=%s",
        request.departure_icao,
        request.arrival_icao,
        request.airline_icao,
        family_id,
        highest_score,
        reliability,
        artifact["version"],
    )

    if reliability_warnings:
        logger.debug(
            "FAMILY ML WARNINGS | %s",
            reliability_warnings,
        )

    return AircraftFamilyPredictionResponse(
        predicted_family_id=family_id,
        predicted_family_name=family_names.get(
            family_id,
            family_id,
        ),
        model_version=str(artifact["version"]),
        candidates=candidates,
        reliability=reliability,
        reliability_warnings=reliability_warnings,
        verified_assignment=False,
    )
