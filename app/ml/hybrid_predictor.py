from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.core.logging import get_logger
from app.ml.aircraft_families import (
    get_aircraft_family,
    get_family_name,
)
from app.ml.family_predictor import load_family_model
from app.ml.features import prediction_features
from app.ml.predictor import load_model
from app.ml.reliability import assess_prediction_reliability
from app.schemas.ml import (
    AircraftFamilyCandidate,
    AircraftPredictionRequest,
    HybridAircraftPredictionResponse,
    HybridAircraftSuggestion,
)


logger = get_logger("ml.hybrid_predictor")

RELIABILITY_ORDER = {
    "unknown": 0,
    "low": 1,
    "moderate": 2,
    "higher": 3,
}

TOP_K = 5
FAMILY_INFLUENCE = 0.50

# Heuristic thresholds, to be tuned on validation data.
MIN_FAMILY_SCORE = 0.35
MIN_VARIANT_SCORE = 0.25
MIN_FUSED_MARGIN = 0.05


@dataclass
class ModelPrediction:
    version: str
    scores: dict[str, float]
    reliability: str
    warnings: list[str]


def get_prediction(
    artifact: dict,
    request: AircraftPredictionRequest,
    features,
) -> ModelPrediction:
    """Evaluate one classifier without truncating its classes."""

    model = artifact["model"]

    classifier = model.named_steps["classifier"]

    classes = [
        str(value)
        for value in classifier.classes_
    ]

    probabilities = model.predict_proba(features)[0]

    if len(classes) != len(probabilities):
        raise ValueError(
            "Classifier classes and probabilities differ."
        )

    scores = {
        name: float(score)
        for name, score in zip(classes, probabilities)
    }

    if not scores:
        raise ValueError(
            "ML classifier returned no predictions."
        )

    ordered = sorted(
        scores.items(),
        key=lambda item: (-item[1], item[0]),
    )

    top_score = ordered[0][1]

    second_score = (
        ordered[1][1]
        if len(ordered) > 1
        else 0.0
    )

    reliability, warnings = assess_prediction_reliability(
        request=request,
        artifact=artifact,
        highest_score=top_score,
        second_score=second_score,
    )

    return ModelPrediction(
        version=str(artifact["version"]),
        scores=scores,
        reliability=reliability,
        warnings=warnings,
    )


def try_load(
    loader,
) -> dict | None:
    """Allow a missing model without hiding corrupt artifacts."""

    try:
        return loader()
    except FileNotFoundError:
        return None


def sorted_scores(
    scores: dict[str, float],
) -> list[tuple[str, float]]:
    return sorted(
        scores.items(),
        key=lambda item: (-item[1], item[0]),
    )


def fuse_scores(
    variant_scores: dict[str, float],
    family_scores: dict[str, float],
) -> dict[str, float]:
    """
    Combine aircraft and family model support.

    Keep aircraft-model evidence as the foundation.
    Apply a family-support multiplier to each aircraft.

    Returned values are ranking scores, not calibrated
    probabilities.
    """

    if not family_scores:
        return dict(variant_scores)

    maximum_family_score = max(
        family_scores.values(),
        default=0.0,
    )

    if maximum_family_score <= 0:
        return dict(variant_scores)

    fused: dict[str, float] = {}

    for aircraft, variant_score in variant_scores.items():
        family = get_aircraft_family(aircraft)

        if family is None:
            # Unknown family receives neutral treatment.
            # Its variant evidence is not discarded.
            multiplier = 1.0
        else:
            family_support = (
                family_scores.get(family, 0.0)
                / maximum_family_score
            )

            multiplier = (
                1.0
                - FAMILY_INFLUENCE
                + FAMILY_INFLUENCE * family_support
            )

        fused[aircraft] = variant_score * multiplier

    total = sum(fused.values())

    if total <= 0:
        return dict(variant_scores)

    # Normalize for consistent score presentation.
    # This is NOT probability calibration.
    return {
        aircraft: value / total
        for aircraft, value in fused.items()
    }


def minimum_reliability(
    first: str,
    second: str,
) -> str:
    return min(
        (first, second),
        key=lambda value: RELIABILITY_ORDER.get(
            value, 0
        ),
    )


def predict_hybrid_aircraft(
    request: AircraftPredictionRequest,
) -> HybridAircraftPredictionResponse:
    """Rank aircraft using both trained ML classifiers."""

    features = prediction_features(request)

    family_artifact = try_load(load_family_model)
    variant_artifact = try_load(load_model)

    if family_artifact is None and variant_artifact is None:
        raise FileNotFoundError(
            "Neither aircraft ML model is available."
        )

    warnings: list[str] = []

    family_prediction = None
    variant_prediction = None

    if family_artifact is not None:
        family_prediction = get_prediction(
            family_artifact,
            request,
            features,
        )
        warnings.extend(family_prediction.warnings)
    else:
        warnings.append(
            "Aircraft-family model is unavailable."
        )

    if variant_artifact is not None:
        variant_prediction = get_prediction(
            variant_artifact,
            request,
            features,
        )
        warnings.extend(variant_prediction.warnings)
    else:
        warnings.append(
            "Aircraft-variant model is unavailable."
        )

    family_scores = (
        family_prediction.scores
        if family_prediction
        else {}
    )

    variant_scores = (
        variant_prediction.scores
        if variant_prediction
        else {}
    )

    ordered_families = sorted_scores(family_scores)
    ordered_variants = sorted_scores(variant_scores)

    family_id: str | None = None
    family_name: str | None = None

    if ordered_families:
        family_id = ordered_families[0][0]
        family_name = get_family_name(family_id)

    # If only the aircraft model exists, provide
    # a family inferred from its leading variant.
    if family_id is None and ordered_variants:
        family_id = get_aircraft_family(
            ordered_variants[0][0]
        )

        if family_id:
            family_name = get_family_name(family_id)
            warnings.append(
                "Aircraft family inferred from the "
                "variant model."
            )

    agreement = "unknown"

    if ordered_families and ordered_variants:
        top_variant = ordered_variants[0][0]
        top_variant_family = get_aircraft_family(
            top_variant
        )

        if top_variant_family is None:
            warnings.append(
                "Leading aircraft variant has no "
                "known family mapping."
            )
        elif top_variant_family == family_id:
            agreement = "agree"
        else:
            agreement = "disagree"
            warnings.append(
                "Family and variant classifiers "
                "disagree on the leading prediction."
            )

    fused = fuse_scores(
        variant_scores,
        family_scores,
    )

    ordered_fused = sorted_scores(fused)

    # Family model supports re-ranking, but does
    # not erase the aircraft model's candidates.
    suggestions = []

    for aircraft, score in ordered_fused[:TOP_K]:
        candidate_family = get_aircraft_family(
            aircraft
        )

        suggestions.append(
            HybridAircraftSuggestion(
                aircraft_icao=aircraft,
                family_id=candidate_family,
                family_name=(
                    get_family_name(candidate_family)
                    if candidate_family
                    else None
                ),
                model_score=round(score, 4),
                matches_predicted_family=(
                    family_id is not None
                    and candidate_family == family_id
                ),
            )
        )

    family_candidates = [
        AircraftFamilyCandidate(
            family_id=family,
            family_name=get_family_name(family),
            model_score=round(score, 4),
        )
        for family, score in ordered_families[:TOP_K]
    ]

    family_reliability = (
        family_prediction.reliability
        if family_prediction
        else "unknown"
    )

    variant_reliability = (
        variant_prediction.reliability
        if variant_prediction
        else "unknown"
    )

    if family_prediction and variant_prediction:
        reliability = minimum_reliability(
            family_reliability,
            variant_reliability,
        )
    else:
        reliability = "low"
        warnings.append(
            "Only one classifier is available; "
            "independent model agreement is unavailable."
        )

    if agreement == "disagree":
        reliability = "low"

    # Do not confuse a strong ranking with a
    # sufficiently reliable exact aircraft selection.
    selected_aircraft: str | None = None

    if (
        family_prediction is not None
        and variant_prediction is not None
        and ordered_fused
    ):
        top_fused_aircraft = ordered_fused[0][0]
        top_fused_score = ordered_fused[0][1]

        second_fused_score = (
            ordered_fused[1][1]
            if len(ordered_fused) > 1
            else 0.0
        )

        top_family_score = (
            ordered_families[0][1]
            if ordered_families
            else 0.0
        )

        original_variant_score = variant_scores.get(
            top_fused_aircraft, 0.0
        )

        candidate_family = get_aircraft_family(
            top_fused_aircraft
        )

        if (
            agreement == "agree"
            and candidate_family == family_id
            and RELIABILITY_ORDER[reliability]
                >= RELIABILITY_ORDER["moderate"]
            and top_family_score >= MIN_FAMILY_SCORE
            and original_variant_score >= MIN_VARIANT_SCORE
            and (
                top_fused_score - second_fused_score
            ) >= MIN_FUSED_MARGIN
        ):
            selected_aircraft = top_fused_aircraft

    if selected_aircraft is None:
        warnings.append(
            "No exact aircraft was selected because "
            "the prediction did not satisfy the "
            "conservative selection criteria."
        )

    unmapped_variants = [
        aircraft
        for aircraft, _ in ordered_variants
        if get_aircraft_family(aircraft) is None
    ]

    if unmapped_variants:
        warnings.append(
            f"{len(unmapped_variants)} aircraft classes "
            "have no registered family mapping."
        )

    logger.info(
        "HYBRID V2 | %s -> %s | airline=%s | "
        "family=%s | selected=%s | agreement=%s | "
        "reliability=%s",
        request.departure_icao,
        request.arrival_icao,
        request.airline_icao,
        family_id or "UNKNOWN",
        selected_aircraft or "NONE",
        agreement,
        reliability,
    )

    return HybridAircraftPredictionResponse(
        predicted_family_id=family_id,
        predicted_family_name=family_name,
        predicted_aircraft_icao=selected_aircraft,
        family_model_version=(
            family_prediction.version
            if family_prediction
            else None
        ),
        variant_model_version=(
            variant_prediction.version
            if variant_prediction
            else None
        ),
        model_agreement=agreement,
        reliability=reliability,
        family_reliability=family_reliability,
        variant_reliability=variant_reliability,
        suggested_variants=suggestions,
        family_candidates=family_candidates,
        warnings=list(dict.fromkeys(warnings)),
        verified_assignment=False,
        prediction_source="historical_ml",
    )
