from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from app.ml.aircraft_families import (
    FAMILY_NAMES,
    get_aircraft_family,
    validate_family_mapping,
)
from app.ml.features import (
    CATEGORICAL_COLUMNS,
    FEATURE_COLUMNS,
    NUMERIC_COLUMNS,
    prepare_features,
)


VERSION = "flightengine-ml-v2"

KEYS = [
    "airline_icao",
    "departure_icao",
    "arrival_icao",
    "aircraft_icao",
]

RANDOM_STATE = 42


def build_pipeline() -> Pipeline:
    """Build a frequency-weighted aircraft classifier."""

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "categorical",
                OneHotEncoder(
                    handle_unknown="ignore",
                ),
                CATEGORICAL_COLUMNS,
            ),
            (
                "numeric",
                "passthrough",
                NUMERIC_COLUMNS,
            ),
        ],
    )

    classifier = RandomForestClassifier(
        n_estimators=250,
        min_samples_leaf=3,
        max_features="sqrt",
        class_weight=None,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )

    return Pipeline([
        ("preprocessing", preprocessor),
        ("classifier", classifier),
    ])


def load_data(
    combined_path: Path,
    detailed_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load historical records and monthly BTS observations."""

    combined = pd.read_csv(
        combined_path,
        dtype={
            "airline_icao": "string",
            "departure_icao": "string",
            "arrival_icao": "string",
            "aircraft_icao": "string",
        },
    )

    detailed = pd.read_csv(
        detailed_path,
        dtype={
            "airline_icao": "string",
            "departure_icao": "string",
            "arrival_icao": "string",
            "aircraft_icao": "string",
        },
    )

    required_combined = set(KEYS) | {
        "distance_nm",
        "source",
    }

    required_detailed = set(KEYS) | {
        "year",
        "month",
        "departures_performed",
    }

    for name, data, required in (
        ("combined", combined, required_combined),
        ("detailed", detailed, required_detailed),
    ):
        missing = required - set(data.columns)

        if missing:
            raise ValueError(
                f"{name} dataset missing: {sorted(missing)}"
            )

    # Only genuine historical records enter the
    # legacy-prior training pool.
    historical = combined.loc[
        combined["source"] != "bts_t100"
    ].copy()

    # Build an airline-route distance lookup.
    # Distance is constant for each airport pair,
    # independent of airline and aircraft variant.
    distances = (
        combined[
            ["departure_icao", "arrival_icao", "distance_nm"]
        ]
        .dropna()
        .drop_duplicates(
            ["departure_icao", "arrival_icao"]
        )
    )

    detailed = detailed.merge(
        distances,
        on=["departure_icao", "arrival_icao"],
        how="left",
        validate="many_to_one",
    )

    detailed["departures_performed"] = pd.to_numeric(
        detailed["departures_performed"],
        errors="coerce",
    )

    detailed["year"] = pd.to_numeric(
        detailed["year"],
        errors="coerce",
    )

    detailed["month"] = pd.to_numeric(
        detailed["month"],
        errors="coerce",
    )

    detailed = detailed.dropna(
        subset=[
            *KEYS,
            "distance_nm",
            "departures_performed",
            "year",
            "month",
        ]
    ).copy()

    detailed = detailed.loc[
        (detailed["departures_performed"] > 0)
        & detailed["month"].between(1, 12)
        & detailed["year"].between(2000, 2100)
    ].copy()

    detailed["year"] = detailed["year"].astype(int)
    detailed["month"] = detailed["month"].astype(int)

    detailed["period"] = pd.to_datetime(
        dict(
            year=detailed["year"],
            month=detailed["month"],
            day=1,
        )
    )

    # Aggregate duplicate reports for the same
    # monthly airline-route-aircraft combination.
    detailed = (
        detailed.groupby(
            [*KEYS, "period"],
            as_index=False,
        )
        .agg(
            distance_nm=("distance_nm", "first"),
            departures_performed=(
                "departures_performed",
                "sum",
            ),
        )
    )

    historical = historical.dropna(
        subset=[*KEYS, "distance_nm"]
    ).copy()

    historical = historical.drop_duplicates(
        subset=KEYS,
    )

    for data in (historical, detailed):
        for column in KEYS:
            data[column] = (
                data[column]
                .astype("string")
                .str.strip()
                .str.upper()
            )

        data["distance_nm"] = pd.to_numeric(
            data["distance_nm"],
            errors="coerce",
        )

    historical = historical.loc[
        historical["distance_nm"].between(
            0.01, 20000
        )
    ].copy()

    detailed = detailed.loc[
        detailed["distance_nm"].between(
            0.01, 20000
        )
    ].copy()

    if detailed.empty:
        raise ValueError(
            "No usable BTS observations were found."
        )

    return historical, detailed


def add_targets(
    data: pd.DataFrame,
    mode: str,
) -> pd.DataFrame:
    result = data.copy()

    if mode == "family":
        result["target"] = (
            result["aircraft_icao"]
            .map(get_aircraft_family)
        )
    else:
        result["target"] = result["aircraft_icao"]

    return result.dropna(
        subset=["target"]
    ).copy()


def calculate_weights(
    data: pd.DataFrame,
    latest_period: pd.Timestamp,
) -> np.ndarray:
    """Weight frequency with diminishing returns and recency."""

    departures = data[
        "departures_performed"
    ].to_numpy(dtype=float)

    months_old = (
        (latest_period.year - data["period"].dt.year)
        * 12
        + latest_period.month
        - data["period"].dt.month
    ).clip(lower=0).to_numpy()

    # Logarithmic weighting prevents large airlines
    # from overwhelming the entire training set.
    frequency_weight = np.log1p(departures)

    # Half-life approximately 12 months.
    recency_weight = np.power(
        0.5,
        months_old / 12.0,
    )

    return frequency_weight * recency_weight


def make_training_data(
    historical: pd.DataFrame,
    recent: pd.DataFrame,
    latest_period: pd.Timestamp,
) -> tuple[pd.DataFrame, np.ndarray]:
    """Combine recent observations with weak historical priors."""

    recent = recent.copy()
    recent_weights = calculate_weights(
        recent,
        latest_period,
    )

    historical = historical.copy()

    # Each historical combination counts as weak
    # prior evidence, not an observed flight count.
    historical_weights = np.ones(
        len(historical),
        dtype=float,
    )

    # Limit all historical evidence to 10% of
    # the recent training weight in aggregate.
    if len(historical_weights):
        historical_weights *= (
            recent_weights.sum()
            * 0.10
            / len(historical_weights)
        )

    combined = pd.concat(
        [recent, historical],
        ignore_index=True,
    )

    weights = np.concatenate([
        recent_weights,
        historical_weights,
    ])

    return combined, weights


def evaluate(
    model: Pipeline,
    test: pd.DataFrame,
) -> dict:
    """Evaluate future-month equipment predictions."""

    X = prepare_features(test)
    y = test["target"].astype(str).to_numpy()

    predicted = model.predict(X)
    probabilities = model.predict_proba(X)

    classes = np.asarray(
        model.named_steps["classifier"].classes_
    )

    k = min(3, len(classes))

    top_indices = np.argsort(
        probabilities,
        axis=1,
    )[:, -k:]

    top_labels = classes[top_indices]

    top3_correct = np.any(
        top_labels == y[:, None],
        axis=1,
    )

    departures = test[
        "departures_performed"
    ].to_numpy(dtype=float)

    correct = predicted == y

    return {
        "accuracy": round(
            float(accuracy_score(y, predicted)),
            4,
        ),
        "balanced_accuracy": round(
            float(
                balanced_accuracy_score(
                    y, predicted,
                )
            ),
            4,
        ),
        "top_3_accuracy": round(
            float(top3_correct.mean()),
            4,
        ),
        "departure_weighted_accuracy": round(
            float(
                np.average(
                    correct,
                    weights=departures,
                )
            ),
            4,
        ),
        "departure_weighted_top_3": round(
            float(
                np.average(
                    top3_correct,
                    weights=departures,
                )
            ),
            4,
        ),
        "test_rows": len(test),
        "test_departures": float(
            departures.sum()
        ),
    }


def train_model(
    historical: pd.DataFrame,
    detailed: pd.DataFrame,
    mode: str,
    output: Path,
) -> dict:
    """Train with an out-of-time BTS holdout."""

    historical = add_targets(historical, mode)
    detailed = add_targets(detailed, mode)

    if detailed.empty:
        raise ValueError(
            f"No usable BTS targets for {mode}."
        )

    periods = sorted(detailed["period"].unique())

    if len(periods) < 2:
        raise ValueError(
            "At least two BTS months are required "
            "for chronological evaluation."
        )

    split_index = max(
        1,
        int(len(periods) * 0.8),
    )

    split_index = min(
        split_index,
        len(periods) - 1,
    )

    cutoff = periods[split_index]

    train_recent = detailed.loc[
        detailed["period"] < cutoff
    ].copy()

    test = detailed.loc[
        detailed["period"] >= cutoff
    ].copy()

    if train_recent.empty or test.empty:
        raise ValueError(
            "Chronological split produced an empty partition."
        )

    # Only evaluate aircraft classes observed in
    # training. Report withheld unsupported classes.
    train_classes = set(
        pd.concat(
            [
                train_recent["target"],
                historical["target"],
            ]
        ).astype(str)
    )

    unseen_mask = ~test[
        "target"
    ].astype(str).isin(train_classes)

    unseen_count = int(unseen_mask.sum())

    # Retain unseen classes in the test set:
    # they must count as errors rather than disappear.

    training, weights = make_training_data(
        historical,
        train_recent,
        latest_period=train_recent["period"].max(),
    )

    X_train = prepare_features(training)
    y_train = training["target"].astype(str)

    if y_train.nunique() < 2:
        raise ValueError(
            "Need at least two target classes."
        )

    model = build_pipeline()

    model.fit(
        X_train,
        y_train,
        classifier__sample_weight=weights,
    )

    metrics = evaluate(model, test)

    majority = (
        train_recent.groupby("target")[
            "departures_performed"
        ]
        .sum()
        .idxmax()
    )

    metrics["baseline_accuracy"] = round(
        float(
            accuracy_score(
                test["target"].astype(str),
                np.repeat(
                    str(majority),
                    len(test),
                ),
            )
        ),
        4,
    )

    metrics["unseen_class_rows"] = unseen_count
    metrics["train_rows"] = len(training)
    metrics["train_recent_rows"] = len(train_recent)
    metrics["train_historical_rows"] = len(historical)
    metrics["train_through"] = str(
        train_recent["period"].max().date()
    )
    metrics["test_from"] = str(
        test["period"].min().date()
    )
    metrics["test_through"] = str(
        test["period"].max().date()
    )

    # Final production model includes all available
    # recent observations, including the holdout.
    # The reported metrics belong to the earlier
    # evaluation model, not this final model.
    production_data, production_weights = (
        make_training_data(
            historical,
            detailed,
            latest_period=detailed["period"].max(),
        )
    )

    X_all = prepare_features(production_data)
    y_all = production_data["target"].astype(str)

    production_model = build_pipeline()

    production_model.fit(
        X_all,
        y_all,
        classifier__sample_weight=production_weights,
    )

    artifact = {
        "version": f"{VERSION}-{mode}",
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "model": production_model,
        "feature_columns": FEATURE_COLUMNS,
        "classes": sorted(y_all.unique().tolist()),
        "trained_rows": len(production_data),
        "known_airlines": sorted(
            X_all["airline_icao"].unique().tolist()
        ),
        "known_airports": sorted(
            set(X_all["departure_icao"])
            | set(X_all["arrival_icao"])
        ),
        "known_routes": sorted(
            (
                X_all["airline_icao"]
                + "|"
                + X_all["departure_icao"]
                + "|"
                + X_all["arrival_icao"]
            ).unique().tolist()
        ),
        "evaluation": metrics,
        "dataset_source": (
            "bts_t100_weighted_plus_openflights"
        ),
        "prediction_verified": False,
        "verified_assignments": False,
    }

    if mode == "family":
        artifact["family_names"] = {
            family: FAMILY_NAMES[family]
            for family in artifact["classes"]
        }

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    joblib.dump(artifact, output)

    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--combined",
        type=Path,
        default=Path(
            "data/ml/aircraft_assignments_v2.csv"
        ),
    )

    parser.add_argument(
        "--detailed",
        type=Path,
        default=Path(
            "data/ml/bts_assignments_detailed.csv"
        ),
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("models/v2"),
    )

    args = parser.parse_args()

    validate_family_mapping()

    historical, detailed = load_data(
        args.combined,
        args.detailed,
    )

    reports = {}

    for mode, filename in (
        ("aircraft", "aircraft_assignment.joblib"),
        ("family", "aircraft_family.joblib"),
    ):
        print(f"\nTraining {mode} V2 model...")

        reports[mode] = train_model(
            historical=historical,
            detailed=detailed,
            mode=mode,
            output=args.output_dir / filename,
        )

        print(
            json.dumps(
                reports[mode],
                indent=2,
            )
        )

    report_path = (
        args.output_dir / "evaluation.json"
    )

    report_path.write_text(
        json.dumps(
            reports,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\nFlightEngine ML V2 training completed.")
    print(f"Models: {args.output_dir}")
    print(f"Evaluation: {report_path}")


if __name__ == "__main__":
    main()
