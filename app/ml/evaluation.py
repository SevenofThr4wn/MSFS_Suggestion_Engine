
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
)

from app.core.logging import get_logger
from app.ml.aircraft_families import (
    get_aircraft_family,
    validate_family_mapping,
)
from app.ml.features import prepare_features
from app.ml.trainer_v2 import (
    add_targets,
    build_pipeline,
    load_data,
    make_training_data,
)


logger = get_logger("ml.evaluation")

FAMILY_INFLUENCE = 0.0

MIN_FAMILY_SCORE = 0.35
MIN_VARIANT_SCORE = 0.25
MIN_FUSED_MARGIN = 0.05

TOP_K = 3

DEFAULT_DETAILED_PATH = Path(
    "data/ml/bts_assignments_detailed.csv"
)


def chronological_split(
    data: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split BTS observations into earlier and later months."""

    periods = sorted(data["period"].unique())

    if len(periods) < 2:
        raise ValueError(
            "At least two observation months are required."
        )

    index = max(1, int(len(periods) * 0.8))
    index = min(index, len(periods) - 1)

    cutoff = periods[index]

    train = data.loc[
        data["period"] < cutoff
    ].copy()

    test = data.loc[
        data["period"] >= cutoff
    ].copy()

    if train.empty or test.empty:
        raise ValueError(
            "Chronological split produced an empty dataset."
        )

    return train, test


def fit_evaluation_model(
    historical: pd.DataFrame,
    recent: pd.DataFrame,
    mode: str,
):
    """
    Fit an evaluation-only classifier.

    The model receives no observations from the
    chronological test period.
    """

    historical = add_targets(historical, mode)
    recent = add_targets(recent, mode)

    training, weights = make_training_data(
        historical,
        recent,
        latest_period=recent["period"].max(),
    )

    X = prepare_features(training)
    y = training["target"].astype(str)

    if y.nunique() < 2:
        raise ValueError(
            f"Insufficient classes for {mode} training."
        )

    model = build_pipeline()

    model.fit(
        X,
        y,
        classifier__sample_weight=weights,
    )

    return model, training


def get_scores(
    model,
    data: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray]:
    """Return classifier classes and prediction scores."""

    features = prepare_features(data)

    scores = np.asarray(
        model.predict_proba(features),
        dtype=float,
    )

    classes = np.asarray(
        model.named_steps["classifier"].classes_,
        dtype=str,
    )

    if scores.shape != (len(data), len(classes)):
        raise ValueError(
            "Classifier returned an invalid score matrix."
        )

    if (
        not np.isfinite(scores).all()
        or (scores < 0).any()
    ):
        raise ValueError(
            "Classifier returned invalid prediction scores."
        )

    return classes, scores


def top_k_predictions(
    classes: np.ndarray,
    scores: np.ndarray,
    k: int = TOP_K,
) -> np.ndarray:
    """Return top-k labels ordered by model score."""

    count = min(k, len(classes))

    indices = np.argsort(
        -scores,
        axis=1,
        kind="stable",
    )[:, :count]

    return classes[indices]


def calculate_metrics(
    actual: np.ndarray,
    candidates: np.ndarray,
    weights: np.ndarray,
) -> dict:
    """Calculate ordinary and departure-weighted metrics."""

    if len(actual) == 0:
        raise ValueError(
            "Cannot evaluate an empty prediction set."
        )

    predicted = candidates[:, 0]

    top1_correct = predicted == actual

    top3_correct = np.any(
        candidates[:, :3] == actual[:, None],
        axis=1,
    )

    return {
        "accuracy": round(
            float(accuracy_score(actual, predicted)),
            4,
        ),
        "balanced_accuracy": round(
            float(
                balanced_accuracy_score(
                    actual,
                    predicted,
                )
            ),
            4,
        ),
        "top_3_accuracy": round(
            float(np.mean(top3_correct)),
            4,
        ),
        "departure_weighted_accuracy": round(
            float(
                np.average(
                    top1_correct,
                    weights=weights,
                )
            ),
            4,
        ),
        "departure_weighted_top_3": round(
            float(
                np.average(
                    top3_correct,
                    weights=weights,
                )
            ),
            4,
        ),
        "test_rows": int(len(actual)),
        "test_departures": float(weights.sum()),
    }


def fuse_distributions(
    aircraft_classes: np.ndarray,
    aircraft_scores: np.ndarray,
    family_classes: np.ndarray,
    family_scores: np.ndarray,
) -> np.ndarray:
    """
    Apply the same family-support multiplier as
    Hybrid Predictor V2.

    Output values are ranking scores, not calibrated
    operating probabilities.
    """

    family_indices = {
        family: index
        for index, family in enumerate(family_classes)
    }

    aircraft_families = [
        get_aircraft_family(code)
        for code in aircraft_classes
    ]

    family_support = np.zeros_like(
        aircraft_scores
    )

    maximum_family_scores = np.maximum(
        family_scores.max(axis=1),
        1e-12,
    )

    multipliers = np.ones(
        len(aircraft_classes),
        dtype=float,
    )

    for column, family in enumerate(aircraft_families):
        if family is None:
            continue

        multipliers[column] = (
            1.0 - FAMILY_INFLUENCE
        )

        family_index = family_indices.get(family)

        if family_index is not None:
            family_support[:, column] = (
                family_scores[:, family_index]
                / maximum_family_scores
            )

    fused = aircraft_scores * (
        multipliers[None, :]
        + FAMILY_INFLUENCE * family_support
        * np.asarray(
            [
                family is not None
                for family in aircraft_families
            ],
            dtype=float,
        )[None, :]
    )

    totals = fused.sum(
        axis=1,
        keepdims=True,
    )

    return np.divide(
        fused,
        totals,
        out=np.zeros_like(fused),
        where=totals > 0,
    )


def reliability_levels(
    scores: np.ndarray,
    known_entities: np.ndarray,
) -> np.ndarray:
    """
    Reproduce the current heuristic reliability levels.

    0 = unknown/unseen
    1 = low
    2 = moderate
    3 = higher

    These are not empirically calibrated confidence levels.
    """

    sorted_scores = np.sort(
        scores,
        axis=1,
    )[:, ::-1]

    highest = sorted_scores[:, 0]

    second = (
        sorted_scores[:, 1]
        if scores.shape[1] > 1
        else np.zeros(len(scores))
    )

    margin = highest - second

    levels = np.full(
        len(scores),
        3,
        dtype=int,
    )

    moderate = (
        (highest < 0.60)
        | (margin < 0.20)
    )

    low = (
        (highest < 0.35)
        | (margin < 0.08)
    )

    levels[moderate] = 2
    levels[low] = 1
    levels[~known_entities] = 1

    return levels


def evaluate_hybrid(
    test: pd.DataFrame,
    aircraft_model,
    family_model,
    aircraft_training: pd.DataFrame,
    family_training: pd.DataFrame,
) -> tuple[dict, pd.DataFrame]:
    """Evaluate hybrid ranking and conservative selection."""

    test = test.copy()

    # Hybrid evaluation requires a known actual
    # aircraft-family label.
    test["actual_family"] = (
        test["aircraft_icao"]
        .map(get_aircraft_family)
    )

    test = test.dropna(
        subset=["actual_family"]
    ).copy()

    if test.empty:
        raise ValueError(
            "No family-mapped test observations available."
        )

    actual = test[
        "aircraft_icao"
    ].astype(str).to_numpy()

    departures = test[
        "departures_performed"
    ].to_numpy(dtype=float)

    aircraft_classes, aircraft_scores = get_scores(
        aircraft_model,
        test,
    )

    family_classes, family_scores = get_scores(
        family_model,
        test,
    )

    fused_scores = fuse_distributions(
        aircraft_classes,
        aircraft_scores,
        family_classes,
        family_scores,
    )

    aircraft_top = top_k_predictions(
        aircraft_classes,
        aircraft_scores,
    )

    family_top = top_k_predictions(
        family_classes,
        family_scores,
    )

    hybrid_top = top_k_predictions(
        aircraft_classes,
        fused_scores,
    )

    top_aircraft_families = np.array(
        [
            get_aircraft_family(code)
            for code in aircraft_top[:, 0]
        ],
        dtype=object,
    )

    agreement = (
        top_aircraft_families
        == family_top[:, 0]
    )

    # Match the coverage check in reliability.py.
    aircraft_airlines = set(
        aircraft_training["airline_icao"]
    )

    aircraft_airports = (
        set(aircraft_training["departure_icao"])
        | set(aircraft_training["arrival_icao"])
    )

    family_airlines = set(
        family_training["airline_icao"]
    )

    family_airports = (
        set(family_training["departure_icao"])
        | set(family_training["arrival_icao"])
    )

    aircraft_coverage = (
        test["airline_icao"].isin(aircraft_airlines)
        & test["departure_icao"].isin(aircraft_airports)
        & test["arrival_icao"].isin(aircraft_airports)
    ).to_numpy()

    family_coverage = (
        test["airline_icao"].isin(family_airlines)
        & test["departure_icao"].isin(family_airports)
        & test["arrival_icao"].isin(family_airports)
    ).to_numpy()

    aircraft_reliability = reliability_levels(
        aircraft_scores,
        aircraft_coverage,
    )

    family_reliability = reliability_levels(
        family_scores,
        family_coverage,
    )

    combined_reliability = np.minimum(
        aircraft_reliability,
        family_reliability,
    )

    combined_reliability[~agreement] = 1

    fused_top_scores = np.sort(
        fused_scores,
        axis=1,
    )[:, ::-1]

    fused_margin = (
        fused_top_scores[:, 0]
        - fused_top_scores[:, 1]
    )

    aircraft_score_lookup = {
        code: index
        for index, code in enumerate(aircraft_classes)
    }

    top_hybrid = hybrid_top[:, 0]

    top_variant_scores = np.array([
        aircraft_scores[
            index,
            aircraft_score_lookup[code],
        ]
        for index, code in enumerate(top_hybrid)
    ])

    top_hybrid_families = np.array(
        [
            get_aircraft_family(code)
            for code in top_hybrid
        ],
        dtype=object,
    )

    selected = (
        agreement
        & (combined_reliability >= 2)
        & (top_hybrid_families == family_top[:, 0])
        & (family_scores.max(axis=1) >= MIN_FAMILY_SCORE)
        & (top_variant_scores >= MIN_VARIANT_SCORE)
        & (fused_margin >= MIN_FUSED_MARGIN)
    )

    selected_correct = (
        selected
        & (top_hybrid == actual)
    )

    results = calculate_metrics(
        actual,
        hybrid_top,
        departures,
    )

    results.update({
        "agreement_rate": round(
            float(agreement.mean()), 4
        ),
        "departure_weighted_agreement_rate": round(
            float(np.average(
                agreement,
                weights=departures,
            )),
            4,
        ),
        "selection_rate": round(
            float(selected.mean()), 4
        ),
        "abstention_rate": round(
            float((~selected).mean()), 4
        ),
        "selected_accuracy": (
            round(
                float(
                    selected_correct.sum()
                    / selected.sum()
                ),
                4,
            )
            if selected.any()
            else None
        ),
        "selected_departure_weighted_accuracy": (
            round(
                float(
                    departures[selected_correct].sum()
                    / departures[selected].sum()
                ),
                4,
            )
            if selected.any()
            else None
        ),
        "agreement_accuracy": (
            round(
                float(
                    (top_hybrid[agreement]
                     == actual[agreement]).mean()
                ),
                4,
            )
            if agreement.any()
            else None
        ),
        "disagreement_accuracy": (
            round(
                float(
                    (top_hybrid[~agreement]
                     == actual[~agreement]).mean()
                ),
                4,
            )
            if (~agreement).any()
            else None
        ),
    })

    details = test[[
        "airline_icao",
        "departure_icao",
        "arrival_icao",
        "period",
        "aircraft_icao",
        "actual_family",
        "departures_performed",
        "distance_nm",
    ]].copy()

    details["predicted_aircraft"] = top_hybrid
    details["predicted_family"] = family_top[:, 0]
    details["model_agreement"] = agreement
    details["selected"] = selected
    details["correct"] = top_hybrid == actual

    for index in range(hybrid_top.shape[1]):
        details[f"candidate_{index + 1}"] = (
            hybrid_top[:, index]
        )

    return results, details


def evaluate_aircraft_model(
    dataset_path: Path,
    output_directory: Path,
    detailed_path: Path = DEFAULT_DETAILED_PATH,
) -> dict:
    """
    Evaluate FlightEngine V2 using a chronological holdout.

    Existing callers may continue using the original
    dataset_path/output_directory arguments.

    No production model artifacts are loaded or overwritten.
    """

    validate_family_mapping()

    historical, detailed = load_data(
        combined_path=Path(dataset_path),
        detailed_path=Path(detailed_path),
    )

    train, test = chronological_split(detailed)

    logger.info(
        "ML V2 EVALUATION | train_through=%s | test_from=%s",
        train["period"].max(),
        test["period"].min(),
    )

    comparison_test = test.copy()

    comparison_test["actual_family"] = (
        comparison_test["aircraft_icao"]
        .map(get_aircraft_family)
    )

    comparison_test = comparison_test.dropna(
        subset=["actual_family"]
    ).copy()

    aircraft_model, aircraft_training = (
        fit_evaluation_model(
            historical,
            train,
            mode="aircraft",
        )
    )

    family_model, family_training = (
        fit_evaluation_model(
            historical,
            train,
            mode="family",
        )
    )

    aircraft_classes, aircraft_scores = get_scores(
        aircraft_model,
        comparison_test,
    )

    aircraft_candidates = top_k_predictions(
        aircraft_classes,
        aircraft_scores,
    )

    aircraft_metrics = calculate_metrics(
        comparison_test["aircraft_icao"]
        .astype(str)
        .to_numpy(),
        aircraft_candidates,
        comparison_test["departures_performed"]
        .to_numpy(dtype=float),
    )

    family_test = test.copy()
    family_test["actual_family"] = (
        family_test["aircraft_icao"]
        .map(get_aircraft_family)
    )

    family_test = family_test.dropna(
        subset=["actual_family"]
    ).copy()

    family_classes, family_scores = get_scores(
        family_model,
        family_test,
    )

    family_candidates = top_k_predictions(
        family_classes,
        family_scores,
    )

    family_metrics = calculate_metrics(
        family_test["actual_family"].astype(str).to_numpy(),
        family_candidates,
        family_test[
            "departures_performed"
        ].to_numpy(dtype=float),
    )

    hybrid_metrics, details = evaluate_hybrid(
        test=test,
        aircraft_model=aircraft_model,
        family_model=family_model,
        aircraft_training=aircraft_training,
        family_training=family_training,
    )

    output_directory = Path(output_directory)

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    report = {
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "evaluation_type": "chronological_bts_holdout",
        "training_through": str(
            train["period"].max().date()
        ),
        "test_from": str(
            test["period"].min().date()
        ),
        "test_through": str(
            test["period"].max().date()
        ),
        "aircraft": aircraft_metrics,
        "family": family_metrics,
        "hybrid": hybrid_metrics,
        "limitations": [
            "BTS coverage is not global.",
            "Model scores are not calibrated probabilities.",
            "The holdout may contain routes seen in training.",
            "Hybrid evaluation excludes aircraft without "
            "family mappings.",
            "Reliability thresholds are heuristic.",
            "Historical OpenFlights records are weak priors.",
        ],
    }

    (output_directory / "evaluation.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    details.to_csv(
        output_directory / "hybrid_predictions.csv",
        index=False,
    )

    logger.info(
        "ML V2 EVALUATION COMPLETE | aircraft=%.4f | "
        "family=%.4f | hybrid=%.4f | hybrid_top3=%.4f",
        aircraft_metrics["accuracy"],
        family_metrics["accuracy"],
        hybrid_metrics["accuracy"],
        hybrid_metrics["top_3_accuracy"],
    )

    return report
