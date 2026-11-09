from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    top_k_accuracy_score,
)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from app.core.logging import get_logger
from app.ml.features import (
    CATEGORICAL_COLUMNS,
    FEATURE_COLUMNS,
    NUMERIC_COLUMNS,
    TARGET_COLUMN,
    prepare_features,
)


logger = get_logger("ml.trainer")

MODEL_VERSION = "aircraft-assignment-v2"

MIN_CLASS_SAMPLES = 10
MIN_CLASS_ROUTES = 5
MIN_TOTAL_ROWS = 40
MIN_UNIQUE_ROUTES = 10
MAX_SPLIT_ATTEMPTS = 100

RANDOM_STATE = 42


def build_pipeline() -> Pipeline:
    """Construct the aircraft assignment classifier."""
    preprocessing = ColumnTransformer(
        transformers=[
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore"),
                CATEGORICAL_COLUMNS,
            ),
            (
                "numeric",
                "passthrough",
                NUMERIC_COLUMNS,
            ),
        ]
    )

    classifier = RandomForestClassifier(
        n_estimators=250,
        min_samples_leaf=3,
        max_features="sqrt",
        class_weight="balanced_subsample",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )

    return Pipeline(
        steps=[
            ("preprocessing", preprocessing),
            ("classifier", classifier),
        ]
    )


def route_groups(features: pd.DataFrame) -> pd.Series:
    """Identify independent airline-route combinations."""
    return (
        features["airline_icao"]
        + "|"
        + features["departure_icao"]
        + "|"
        + features["arrival_icao"]
    )


def filter_rare_aircraft(
    dataset: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    """Exclude aircraft classes lacking sufficient examples."""
    dataset = dataset.copy()

    dataset[TARGET_COLUMN] = (
        dataset[TARGET_COLUMN]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    features = prepare_features(dataset)
    groups = route_groups(features)

    class_counts = dataset[TARGET_COLUMN].value_counts()

    class_routes = (
        pd.DataFrame(
            {
                "aircraft": dataset[TARGET_COLUMN],
                "route": groups,
            }
        )
        .groupby("aircraft")["route"]
        .nunique()
    )

    eligible_classes = {
        aircraft
        for aircraft, count in class_counts.items()
        if (
            count >= MIN_CLASS_SAMPLES
            and class_routes.get(aircraft, 0)
            >= MIN_CLASS_ROUTES
        )
    }

    filtered = dataset[
        dataset[TARGET_COLUMN].isin(eligible_classes)
    ].copy()

    filtered.reset_index(drop=True, inplace=True)

    summary = {
        "original_rows": len(dataset),
        "filtered_rows": len(filtered),
        "removed_rows": len(dataset) - len(filtered),
        "original_classes": len(class_counts),
        "retained_classes": len(eligible_classes),
        "removed_classes": sorted(
            set(class_counts.index) - eligible_classes
        ),
    }

    return filtered, summary


def select_evaluation_split(
    features: pd.DataFrame,
    targets: pd.Series,
    groups: pd.Series,
) -> tuple:
    """Find a group-disjoint split with trainable target classes."""
    splitter = GroupShuffleSplit(
        n_splits=MAX_SPLIT_ATTEMPTS,
        test_size=0.2,
        random_state=RANDOM_STATE,
    )

    for train_idx, test_idx in splitter.split(
        features,
        targets,
        groups=groups,
    ):
        y_train = targets.iloc[train_idx]
        y_test = targets.iloc[test_idx]

        # Every test class must be represented in training.
        if not set(y_test).issubset(set(y_train)):
            continue

        if y_test.nunique() < 2 or y_train.nunique() < 2:
            continue

        return train_idx, test_idx

    raise ValueError(
        "Unable to create an evaluation split with adequate "
        "aircraft-class coverage. Add more diverse route data "
        "or adjust the minimum class thresholds."
    )


def evaluate_model(
    pipeline: Pipeline,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> dict:
    """Calculate aircraft classification metrics."""
    predictions = pipeline.predict(X_test)
    probabilities = pipeline.predict_proba(X_test)

    classes = pipeline.named_steps[
        "classifier"
    ].classes_

    k = min(3, len(classes))

    metrics = {
        "accuracy": round(
            float(accuracy_score(y_test, predictions)),
            4,
        ),
        "balanced_accuracy": round(
            float(balanced_accuracy_score(y_test, predictions)),
            4,
        ),
    }

    if len(classes) > k:
        metrics["top_3_accuracy"] = round(
            float(
                top_k_accuracy_score(
                    y_test,
                    probabilities,
                    k=k,
                    labels=classes,
                )
            ),
            4,
        )
    else:
        metrics["top_3_accuracy"] = 1.0

    return metrics


def train_aircraft_model(
    dataset_path: Path,
    output_path: Path,
) -> dict:
    """Train, evaluate and persist the aircraft model."""
    if not dataset_path.is_file():
        raise FileNotFoundError(
            f"Training dataset not found: {dataset_path}"
        )

    dataset = pd.read_csv(
        dataset_path,
        dtype={
            "airline_icao": "string",
            "departure_icao": "string",
            "arrival_icao": "string",
            "aircraft_icao": "string",
            "source": "string",
            "source_reference": "string",
        },
    )

    required = {
        *FEATURE_COLUMNS,
        TARGET_COLUMN,
        "source",
        "source_reference",
    }

    missing = required - set(dataset.columns)

    if missing:
        raise ValueError(
            f"Missing training columns: {sorted(missing)}"
        )

    for column in (
        TARGET_COLUMN,
        "source",
        "source_reference",
    ):
        values = dataset[column].astype("string").str.strip()

        if values.isna().any() or values.eq("").any():
            raise ValueError(
                f"Training column '{column}' has missing values."
            )

    if dataset.duplicated(
        subset=[
            "airline_icao",
            "departure_icao",
            "arrival_icao",
            TARGET_COLUMN,
        ]
    ).any():
        raise ValueError(
            "Dataset contains duplicate airline-route-aircraft "
            "combinations. Deduplicate before training."
        )

    dataset, filtering = filter_rare_aircraft(dataset)

    if len(dataset) < MIN_TOTAL_ROWS:
        raise ValueError(
            "Not enough training rows after filtering."
        )

    X = prepare_features(dataset)
    y = dataset[TARGET_COLUMN]

    if y.nunique() < 2:
        raise ValueError(
            "At least two aircraft classes are required."
        )

    groups = route_groups(X)

    if groups.nunique() < MIN_UNIQUE_ROUTES:
        raise ValueError(
            "Not enough distinct airline-route combinations."
        )

    train_idx, test_idx = select_evaluation_split(
        X,
        y,
        groups,
    )

    X_train = X.iloc[train_idx]
    X_test = X.iloc[test_idx]

    y_train = y.iloc[train_idx]
    y_test = y.iloc[test_idx]

    logger.info(
        "ML TRAINING | total=%d | train=%d | test=%d | "
        "aircraft_classes=%d",
        len(X),
        len(X_train),
        len(X_test),
        y.nunique(),
    )

    pipeline = build_pipeline()
    pipeline.fit(X_train, y_train)

    evaluation = evaluate_model(
        pipeline,
        X_test,
        y_test,
    )

    # Baseline: always predict the most frequent training class.
    baseline = DummyClassifier(strategy="most_frequent")
    baseline.fit(X_train, y_train)

    baseline_predictions = baseline.predict(X_test)

    evaluation["baseline_accuracy"] = round(
        float(
            accuracy_score(
                y_test,
                baseline_predictions,
            )
        ),
        4,
    )

    evaluation["baseline_balanced_accuracy"] = round(
        float(
            balanced_accuracy_score(
                y_test,
                baseline_predictions,
            )
        ),
        4,
    )

    evaluation.update(
        {
            "train_rows": len(X_train),
            "test_rows": len(X_test),
            "distinct_train_routes": int(
                groups.iloc[train_idx].nunique()
            ),
            "distinct_test_routes": int(
                groups.iloc[test_idx].nunique()
            ),
            "aircraft_classes": int(y.nunique()),
            "filtering": filtering,
        }
    )

    logger.info(
        "ML EVALUATION | accuracy=%.4f | "
        "balanced=%.4f | top3=%.4f | baseline=%.4f",
        evaluation["accuracy"],
        evaluation["balanced_accuracy"],
        evaluation["top_3_accuracy"],
        evaluation["baseline_accuracy"],
    )

    # Train the final inference model on all eligible rows.
    production_pipeline = build_pipeline()
    production_pipeline.fit(X, y)

    artifact = {
        "version": MODEL_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": production_pipeline,
        "feature_columns": FEATURE_COLUMNS,
        "trained_rows": len(X),
        "classes": sorted(y.unique().tolist()),

        # Training coverage metadata
        "known_airlines": sorted(
            X["airline_icao"].unique().tolist()
        ),
        "known_airports": sorted(
            set(X["departure_icao"])
            | set(X["arrival_icao"])
        ),

        "class_counts": {
            str(key): int(value)
            for key, value in Counter(y).items()
        },
        "evaluation": evaluation,
        "dataset_source": "historical_openflights",
        "prediction_verified": False,
    }

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    joblib.dump(artifact, output_path)

    logger.info(
        "ML MODEL SAVED | version=%s | path=%s",
        MODEL_VERSION,
        output_path,
    )

    return evaluation
