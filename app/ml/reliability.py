
from __future__ import annotations

import math
from typing import Final

from app.schemas.ml import AircraftPredictionRequest


# ============================================================
# Reliability Configuration
# ============================================================

RELIABILITY_UNKNOWN: Final[str] = "unknown"
RELIABILITY_LOW: Final[str] = "low"
RELIABILITY_MODERATE: Final[str] = "moderate"
RELIABILITY_HIGHER: Final[str] = "higher"

RELIABILITY_ORDER: Final[dict[str, int]] = {
    RELIABILITY_UNKNOWN: 0,
    RELIABILITY_LOW: 1,
    RELIABILITY_MODERATE: 2,
    RELIABILITY_HIGHER: 3,
}

# Heuristic thresholds retained for compatibility
# with the current V2 evaluation pipeline.
#
# These are NOT calibrated confidence probabilities.

LOW_SCORE_THRESHOLD: Final[float] = 0.35
LOW_MARGIN_THRESHOLD: Final[float] = 0.08

HIGHER_SCORE_THRESHOLD: Final[float] = 0.60
HIGHER_MARGIN_THRESHOLD: Final[float] = 0.20


# ============================================================
# Reliability Utilities
# ============================================================

def normalize_codes(
    values: object,
) -> set[str]:
    """
    Normalize training coverage identifiers.

    Returns an empty set when metadata is missing
    or has an invalid structure.
    """

    if not isinstance(
        values,
        (list, tuple, set, frozenset),
    ):
        return set()

    return {
        value.strip().upper()
        for value in values
        if isinstance(value, str) and value.strip()
    }


def validate_prediction_scores(
    highest_score: float,
    second_score: float,
) -> None:
    """Validate leading classifier score values."""

    scores = (highest_score, second_score)

    if not all(
        math.isfinite(score)
        for score in scores
    ):
        raise ValueError(
            "Prediction scores must be finite."
        )

    if not all(
        0.0 <= score <= 1.0
        for score in scores
    ):
        raise ValueError(
            "Prediction scores must be between 0 and 1."
        )

    if second_score > highest_score:
        raise ValueError(
            "Second prediction score cannot exceed "
            "the leading prediction score."
        )


def lower_reliability(
    first: str,
    second: str,
) -> str:
    """Return the more conservative reliability level."""

    return min(
        (first, second),
        key=lambda value: RELIABILITY_ORDER.get(
            value,
            0,
        ),
    )


# ============================================================
# Training Coverage Assessment
# ============================================================

def assess_training_coverage(
    request: AircraftPredictionRequest,
    artifact: dict,
) -> tuple[str, list[str]]:
    """
    Assess whether the request's identifiers were
    represented in the training data.

    Individual identifier coverage does not establish
    that the exact airline-route pair was observed.
    """

    warnings: list[str] = []

    known_airlines = normalize_codes(
        artifact.get("known_airlines")
    )

    known_airports = normalize_codes(
        artifact.get("known_airports")
    )

    if not known_airlines or not known_airports:
        return (
            RELIABILITY_UNKNOWN,
            [
                "Training coverage metadata is "
                "missing or incomplete."
            ],
        )

    airline = request.airline_icao.strip().upper()
    departure = request.departure_icao.strip().upper()
    arrival = request.arrival_icao.strip().upper()

    if airline not in known_airlines:
        warnings.append(
            "Airline was not represented in training data."
        )

    if departure not in known_airports:
        warnings.append(
            "Departure airport was not represented "
            "in training data."
        )

    if arrival not in known_airports:
        warnings.append(
            "Arrival airport was not represented "
            "in training data."
        )

    if warnings:
        return RELIABILITY_LOW, warnings

    # Optional route-level metadata for future models.
    #
    # Existing V2 artifacts do not include known_routes.
    # Route coverage is therefore unknown rather than
    # automatically being treated as verified.
    if "known_routes" in artifact:
        known_routes = normalize_codes(
            artifact["known_routes"]
        )

        route_key = (
            f"{airline}|{departure}|{arrival}"
        )

        if route_key not in known_routes:
            warnings.append(
                "This exact airline-route combination "
                "was not represented in training data."
            )

            return RELIABILITY_LOW, warnings

    return RELIABILITY_HIGHER, warnings


# ============================================================
# Prediction Ambiguity Assessment
# ============================================================

def assess_score_reliability(
    highest_score: float,
    second_score: float,
) -> tuple[str, list[str]]:
    """
    Assess how strongly the classifier distinguishes
    its two leading candidates.

    This is a heuristic ambiguity measure, not
    an empirically calibrated accuracy estimate.
    """

    validate_prediction_scores(
        highest_score,
        second_score,
    )

    margin = highest_score - second_score

    if (
        highest_score < LOW_SCORE_THRESHOLD
        or margin < LOW_MARGIN_THRESHOLD
    ):
        return (
            RELIABILITY_LOW,
            [
                "Model scores do not strongly "
                "distinguish the leading aircraft "
                "candidates."
            ],
        )

    if (
        highest_score < HIGHER_SCORE_THRESHOLD
        or margin < HIGHER_MARGIN_THRESHOLD
    ):
        return RELIABILITY_MODERATE, []

    return RELIABILITY_HIGHER, []


# ============================================================
# Main Reliability Assessment
# ============================================================

def assess_prediction_reliability(
    request: AircraftPredictionRequest,
    artifact: dict,
    highest_score: float,
    second_score: float,
) -> tuple[str, list[str]]:
    """
    Assess the reliability of an aircraft ML prediction.

    Combines:
        - Training identifier coverage
        - Optional airline-route coverage
        - Leading model score
        - Score margin

    Returns
    -------
    tuple[str, list[str]]
        Reliability label and explanatory warnings.

    Notes
    -----
    Reliability labels are heuristic.

    They are not calibrated probabilities and do not
    verify current airline equipment assignments.
    """

    validate_prediction_scores(
        highest_score,
        second_score,
    )

    coverage_level, coverage_warnings = (
        assess_training_coverage(
            request=request,
            artifact=artifact,
        )
    )

    score_level, score_warnings = (
        assess_score_reliability(
            highest_score=highest_score,
            second_score=second_score,
        )
    )

    reliability = lower_reliability(
        coverage_level,
        score_level,
    )

    warnings = list(
        dict.fromkeys(
            coverage_warnings + score_warnings
        )
    )

    return reliability, warnings
