
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sklearn.dummy import DummyClassifier
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
)
from sklearn.model_selection import GroupShuffleSplit

from app.core.logging import get_logger
from app.ml.aircraft_families import (
    FAMILY_NAMES,
    get_aircraft_family,
    validate_family_mapping,
)
from app.ml.features import (
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    prepare_features,
)
from app.ml.trainer import build_pipeline, route_groups


logger = get_logger("ml.family_trainer")

MODEL_VERSION = "aircraft-family-v1"
MIN_FAMILY_SAMPLES = 20
MIN_FAMILY_ROUTES = 10


def train_family_model(
    dataset_path: Path,
    output_path: Path,
) -> dict:
    """Train and evaluate the aircraft-family model."""
    validate_family_mapping()

    if not dataset_path.is_file():
        raise FileNotFoundError(
            f"Training dataset not found: {dataset_path}"
        )

    data = pd.read_csv(
        dataset_path,
        dtype={
            "airline_icao": "string",
            "departure_icao": "string",
            "arrival_icao": "string",
            "aircraft_icao": "string",
        },
    )

    required = set(FEATURE_COLUMNS) | {TARGET_COLUMN}
    missing = required - set(data.columns)

    if missing:
        raise ValueError(
            f"Missing dataset columns: {sorted(missing)}"
        )

    data["family_id"] = (
        data[TARGET_COLUMN]
        .map(get_aircraft_family)
    )

    unmapped = (
        data.loc[data["family_id"].isna(), TARGET_COLUMN]
        .value_counts()
        .to_dict()
    )

    mapped = data.dropna(subset=["family_id"]).copy()
    X_mapped = prepare_features(mapped)
    mapped["route_group"] = route_groups(X_mapped).to_numpy()

    family_counts = mapped["family_id"].value_counts()
    family_route_counts = (
        mapped.groupby("family_id")["route_group"]
        .nunique()
    )

    eligible = {
        family
        for family, count in family_counts.items()
        if (
            count >= MIN_FAMILY_SAMPLES
            and family_route_counts[family] >= MIN_FAMILY_ROUTES
        )
    }

    data = mapped[
        mapped["family_id"].isin(eligible)
    ].copy().reset_index(drop=True)

    if len(data) < 100 or data["family_id"].nunique() < 2:
        raise ValueError(
            "Insufficient family training data after filtering."
        )

    X = prepare_features(data)
    y = data["family_id"].astype(str)
    groups = route_groups(X)

    if groups.nunique() < 10:
        raise ValueError(
            "At least 10 independent airline-route groups are required."
        )

    splitter = GroupShuffleSplit(
        n_splits=1,
        test_size=0.2,
        random_state=42,
    )

    train_idx, test_idx = next(
        splitter.split(X, y, groups=groups)
    )

    X_train = X.iloc[train_idx]
    X_test = X.iloc[test_idx]
    y_train = y.iloc[train_idx]
    y_test = y.iloc[test_idx]

    model = build_pipeline()
    model.fit(X_train, y_train)

    predicted = model.predict(X_test)
    probabilities = model.predict_proba(X_test)
    classes = np.asarray(
        model.named_steps["classifier"].classes_
    )

    top_indices = np.argsort(probabilities, axis=1)[
        :, -min(3, len(classes)):
    ]
    top_labels = classes[top_indices]

    baseline = DummyClassifier(strategy="most_frequent")
    baseline.fit(X_train, y_train)

    train_classes = set(y_train)
    unseen = (~y_test.isin(train_classes)).sum()

    evaluation = {
        "accuracy": round(
            float(accuracy_score(y_test, predicted)), 4
        ),
        "balanced_accuracy": round(
            float(balanced_accuracy_score(y_test, predicted)), 4
        ),
        "top_3_accuracy": round(
            float(
                np.mean(
                    np.any(
                        top_labels == y_test.to_numpy()[:, None],
                        axis=1,
                    )
                )
            ),
            4,
        ),
        "baseline_accuracy": round(
            float(
                accuracy_score(
                    y_test,
                    baseline.predict(X_test),
                )
            ),
            4,
        ),
        "unseen_class_rows": int(unseen),
        "train_rows": len(X_train),
        "test_rows": len(X_test),
        "family_classes": int(y.nunique()),
        "excluded_unmapped_rows": int(
            len(mapped) + sum(unmapped.values()) - len(mapped)
        ),
        "excluded_rare_family_rows": len(mapped) - len(data),
    }

    logger.info(
        "FAMILY EVALUATION | accuracy=%.4f | "
        "top3=%.4f | baseline=%.4f | families=%d",
        evaluation["accuracy"],
        evaluation["top_3_accuracy"],
        evaluation["baseline_accuracy"],
        evaluation["family_classes"],
    )

    production_model = build_pipeline()
    production_model.fit(X, y)

    artifact = {
        "version": MODEL_VERSION,
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "model": production_model,
        "classes": sorted(y.unique().tolist()),
        "family_names": {
            key: FAMILY_NAMES[key]
            for key in sorted(y.unique())
        },
        "trained_rows": len(data),
        "known_airlines": sorted(
            X["airline_icao"].unique().tolist()
        ),
        "known_airports": sorted(
            set(X["departure_icao"])
            | set(X["arrival_icao"])
        ),
        "class_counts": dict(Counter(y)),
        "evaluation": evaluation,
        "unmapped_aircraft": unmapped,
        "verified_assignments": False,
    }

    output_path.parent.mkdir(
        parents=True, exist_ok=True
    )
    joblib.dump(artifact, output_path)

    logger.info(
        "FAMILY MODEL SAVED | path=%s | rows=%d",
        output_path,
        len(data),
    )

    return evaluation
