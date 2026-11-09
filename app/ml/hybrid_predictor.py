
from __future__ import annotations

from app.core.logging import get_logger

from app.ml.aircraft_families import (
    get_aircraft_family,
    get_family_name,
)
from app.ml.family_predictor import (
    predict_aircraft_family,
)
from app.ml.predictor import predict_aircraft

from app.schemas.ml import (
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


def lower_reliability(
    first: str,
    second: str,
) -> str:
    """Return the more conservative reliability label."""
    return min(
        (first, second),
        key=lambda value: RELIABILITY_ORDER.get(value, 0),
    )


def predict_hybrid_aircraft(
    request: AircraftPredictionRequest,
) -> HybridAircraftPredictionResponse:
    """Combine aircraft-family and variant predictions."""

    warnings: list[str] = []

    family_result = None
    variant_result = None

    # Load and query the models independently.
    # A missing artifact should not disable the other model.
    try:
        family_result = predict_aircraft_family(request)
    except FileNotFoundError:
        warnings.append(
            "Aircraft-family model is not available."
        )

    try:
        variant_result = predict_aircraft(request)
    except FileNotFoundError:
        warnings.append(
            "Aircraft-variant model is not available."
        )

    if family_result is None and variant_result is None:
        raise FileNotFoundError(
            "Neither aircraft ML model is available."
        )

    family_id: str | None = None
    family_name: str | None = None

    family_version: str | None = None
    variant_version: str | None = None

    family_candidates = []
    variant_candidates = []

    family_reliability = "unknown"
    variant_reliability = "unknown"

    if family_result is not None:
        family_id = family_result.predicted_family_id
        family_name = family_result.predicted_family_name
        family_version = family_result.model_version
        family_candidates = family_result.candidates

        family_reliability = family_result.reliability

        warnings.extend(
            family_result.reliability_warnings
        )

    if variant_result is not None:
        variant_version = variant_result.model_version
        variant_candidates = variant_result.candidates

        variant_reliability = variant_result.reliability

        warnings.extend(
            variant_result.reliability_warnings
        )

    # Derive a family from the top variant if the family
    # classifier isn't available.
    if family_id is None and variant_candidates:
        inferred_family = get_aircraft_family(
            variant_candidates[0].aircraft_icao
        )

        if inferred_family:
            family_id = inferred_family
            family_name = get_family_name(inferred_family)

            warnings.append(
                "Aircraft family was inferred from the variant "
                "model rather than predicted independently."
            )

    # Determine whether the top predictions agree.
    agreement = "unknown"

    if (
        family_result is not None
        and variant_result is not None
        and variant_candidates
    ):
        top_variant_family = get_aircraft_family(
            variant_candidates[0].aircraft_icao
        )

        if top_variant_family is None:
            warnings.append(
                "Top predicted aircraft has no known family mapping."
            )
        elif top_variant_family == family_id:
            agreement = "agree"
        else:
            agreement = "disagree"

            warnings.append(
                "Aircraft-family and variant models disagree "
                "on the leading prediction."
            )

    # Build variant suggestions.
    suggestions: list[HybridAircraftSuggestion] = []

    for candidate in variant_candidates:
        candidate_family = get_aircraft_family(
            candidate.aircraft_icao
        )

        suggestions.append(
            HybridAircraftSuggestion(
                aircraft_icao=candidate.aircraft_icao,
                family_id=candidate_family,
                family_name=(
                    get_family_name(candidate_family)
                    if candidate_family
                    else None
                ),
                model_score=candidate.model_score,
                matches_predicted_family=(
                    family_id is not None
                    and candidate_family == family_id
                ),
            )
        )

    # A specific variant is selected only when it matches
    # the independently predicted family, or when operating
    # with the variant model alone.
    predicted_variant = None

    if suggestions:
        if family_result is None:
            predicted_variant = suggestions[0].aircraft_icao
        elif agreement == "agree":
            predicted_variant = suggestions[0].aircraft_icao

    # Resolve the reliability conservatively.
    if family_result and variant_result:
        reliability = lower_reliability(
            family_reliability,
            variant_reliability,
        )
    elif family_result:
        reliability = family_reliability
    else:
        reliability = variant_reliability

    # Disagreement or unknown family coverage limits
    # the usefulness of an exact variant suggestion.
    if agreement == "disagree":
        reliability = "low"

    if family_result is None or variant_result is None:
        warnings.append(
            "Hybrid verification is incomplete because "
            "only one ML model is available."
        )

    logger.info(
        "HYBRID PREDICTION | %s -> %s | "
        "airline=%s | family=%s | variant=%s | "
        "agreement=%s | reliability=%s",
        request.departure_icao,
        request.arrival_icao,
        request.airline_icao,
        family_id or "UNKNOWN",
        predicted_variant or "UNKNOWN",
        agreement,
        reliability,
    )

    return HybridAircraftPredictionResponse(
        predicted_family_id=family_id,
        predicted_family_name=family_name,
        predicted_aircraft_icao=predicted_variant,
        family_model_version=family_version,
        variant_model_version=variant_version,
        model_agreement=agreement,
        reliability=reliability,
        family_reliability=family_reliability,
        variant_reliability=variant_reliability,
        suggested_variants=suggestions,
        family_candidates=family_candidates,
        warnings=list(dict.fromkeys(warnings)),
)
