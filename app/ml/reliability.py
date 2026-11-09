
from __future__ import annotations

from app.schemas.ml import AircraftPredictionRequest


def assess_prediction_reliability(
    request: AircraftPredictionRequest,
    artifact: dict,
    highest_score: float,
    second_score: float,
) -> tuple[str, list[str]]:
    """Assess training coverage and prediction ambiguity."""
    warnings: list[str] = []

    known_airlines = set(
        artifact.get("known_airlines", [])
    )

    known_airports = set(
        artifact.get("known_airports", [])
    )

    if not known_airlines or not known_airports:
        warnings.append(
            "Training coverage metadata is unavailable."
        )

        return "unknown", warnings

    if request.airline_icao not in known_airlines:
        warnings.append(
            "Airline was not represented in training data."
        )

    if request.departure_icao not in known_airports:
        warnings.append(
            "Departure airport was not represented in training."
        )

    if request.arrival_icao not in known_airports:
        warnings.append(
            "Arrival airport was not represented in training."
        )

    if warnings:
        return "low", warnings

    margin = highest_score - second_score

    # Heuristic ambiguity labels, not calibrated confidence.
    if highest_score < 0.35 or margin < 0.08:
        warnings.append(
            "Model scores do not strongly distinguish "
            "the leading aircraft candidates."
        )

        return "low", warnings

    if highest_score < 0.60 or margin < 0.20:
        return "moderate", warnings

    return "higher", warnings
