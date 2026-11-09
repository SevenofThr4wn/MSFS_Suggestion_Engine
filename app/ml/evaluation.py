
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
)
from sklearn.model_selection import GroupShuffleSplit

from app.core.logging import get_logger
from app.ml.features import (
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    prepare_features,
)
from app.ml.trainer import (
    build_pipeline,
    filter_rare_aircraft,
    route_groups,
)


logger = get_logger("ml.evaluation")

RANDOM_STATE = 42
EVALUATION_SPLITS = 3
TEST_SIZE = 0.2

SCORE_BINS = [
    (0.0, 0.2),
    (0.2, 0.4),
    (0.4, 0.6),
    (0.6, 0.8),
    (0.8, 1.0),
]


def write_csv(
    path: Path,
    rows: list[dict],
    columns: list[str],
) -> None:
    """Write a report with deterministic columns."""
    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=columns,
        )
        writer.writeheader()
        writer.writerows(rows)


def evaluate_aircraft_model(
    dataset_path: Path,
    output_directory: Path,
) -> dict:
    """Evaluate aircraft predictions on unseen route groups."""
    if not dataset_path.is_file():
        raise FileNotFoundError(
            f"Dataset not found: {dataset_path}"
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
            f"Missing dataset columns: {sorted(missing)}"
        )

    for column in required:
        if dataset[column].isna().any():
            raise ValueError(
                f"Missing values in column: {column}"
            )

    dataset, filtering = filter_rare_aircraft(dataset)

    if len(dataset) < 40:
        raise ValueError(
            "Insufficient rows after rare-class filtering."
        )

    X = prepare_features(dataset)
    y = dataset[TARGET_COLUMN].astype(str)
    groups = route_groups(X)

    if y.nunique() < 2 or groups.nunique() < 10:
        raise ValueError(
            "Dataset lacks sufficient aircraft or route diversity."
        )

    splitter = GroupShuffleSplit(
        n_splits=EVALUATION_SPLITS,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
    )

    split_results = []

    # Aggregated over evaluation splits; individual rows can
    # appear in test sets more than once across different splits.
    per_class = defaultdict(
        lambda: Counter()
    )
    confusion = Counter()
    reliability = defaultdict(
        lambda: {"total": 0, "correct": 0, "score_sum": 0.0}
    )

    for split_number, (train_idx, test_idx) in enumerate(
        splitter.split(X, y, groups=groups),
        start=1,
    ):
        X_train = X.iloc[train_idx]
        X_test = X.iloc[test_idx]

        y_train = y.iloc[train_idx].to_numpy()
        y_test = y.iloc[test_idx].to_numpy()

        train_groups = set(groups.iloc[train_idx])
        test_groups = set(groups.iloc[test_idx])

        if train_groups & test_groups:
            raise RuntimeError(
                "Evaluation contains overlapping route groups."
            )

        logger.info(
            "ML EVALUATION | split=%d/%d | train=%d | test=%d",
            split_number,
            EVALUATION_SPLITS,
            len(train_idx),
            len(test_idx),
        )

        pipeline = build_pipeline()
        pipeline.fit(X_train, y_train)

        predictions = pipeline.predict(X_test)
        probabilities = pipeline.predict_proba(X_test)

        classes = np.asarray(
            pipeline.named_steps["classifier"].classes_,
        )

        # Compute top-k membership directly so aircraft classes
        # absent from training count as incorrect rather than
        # causing the metric calculation to fail.
        top_k = min(3, len(classes))

        top_indices = np.argsort(
            probabilities,
            axis=1,
        )[:, -top_k:]

        top_labels = classes[top_indices]

        top3_correct = np.any(
            top_labels == y_test[:, None],
            axis=1,
        )

        correct = predictions == y_test
        max_scores = np.max(probabilities, axis=1)

        train_classes = set(y_train)
        unseen_mask = np.asarray(
            [label not in train_classes for label in y_test],
            dtype=bool,
        )

        majority_class = Counter(y_train).most_common(1)[0][0]
        baseline_predictions = np.full(
            len(y_test),
            majority_class,
            dtype=object,
        )

        split_result = {
            "split": split_number,
            "train_rows": len(train_idx),
            "test_rows": len(test_idx),
            "train_routes": len(train_groups),
            "test_routes": len(test_groups),
            "accuracy": float(
                accuracy_score(y_test, predictions)
            ),
            "balanced_accuracy": float(
                balanced_accuracy_score(
                    y_test,
                    predictions,
                )
            ),
            "top_3_accuracy": float(
                np.mean(top3_correct)
            ),
            "baseline_accuracy": float(
                accuracy_score(
                    y_test,
                    baseline_predictions,
                )
            ),
            "unseen_class_rows": int(
                unseen_mask.sum()
            ),
            "unseen_class_fraction": float(
                unseen_mask.mean()
            ),
        }

        split_results.append(split_result)

        for actual, predicted, score, is_correct in zip(
            y_test,
            predictions,
            max_scores,
            correct,
        ):
            actual = str(actual)
            predicted = str(predicted)

            per_class[actual]["support"] += 1

            if is_correct:
                per_class[actual]["tp"] += 1
            else:
                per_class[actual]["fn"] += 1
                per_class[predicted]["fp"] += 1

            confusion[(actual, predicted)] += 1

            for lower, upper in SCORE_BINS:
                if lower <= score < upper or (
                    upper == 1.0 and score == 1.0
                ):
                    key = f"{lower:.1f}-{upper:.1f}"
                    bucket = reliability[key]
                    bucket["total"] += 1
                    bucket["correct"] += int(is_correct)
                    bucket["score_sum"] += float(score)
                    break

    per_aircraft_rows = []

    for aircraft in sorted(per_class):
        counts = per_class[aircraft]

        tp = counts["tp"]
        fp = counts["fp"]
        fn = counts["fn"]

        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0

        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )

        per_aircraft_rows.append(
            {
                "aircraft_icao": aircraft,
                "support": counts["support"],
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1": round(f1, 4),
            }
        )

    per_aircraft_rows.sort(
        key=lambda item: item["support"],
        reverse=True,
    )

    confusion_rows = [
        {
            "actual": actual,
            "predicted": predicted,
            "count": count,
        }
        for (actual, predicted), count in confusion.most_common()
    ]

    reliability_rows = []

    for lower, upper in SCORE_BINS:
        name = f"{lower:.1f}-{upper:.1f}"
        bucket = reliability[name]
        total = bucket["total"]

        reliability_rows.append(
            {
                "score_range": name,
                "count": total,
                "mean_model_score": (
                    round(bucket["score_sum"] / total, 4)
                    if total else None
                ),
                "observed_accuracy": (
                    round(bucket["correct"] / total, 4)
                    if total else None
                ),
            }
        )

    metric_names = [
        "accuracy",
        "balanced_accuracy",
        "top_3_accuracy",
        "baseline_accuracy",
        "unseen_class_fraction",
    ]

    summary = {
        metric: {
            "mean": round(
                float(np.mean([s[metric] for s in split_results])),
                4,
            ),
            "std": round(
                float(np.std([s[metric] for s in split_results])),
                4,
            ),
        }
        for metric in metric_names
    }

    report = {
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "evaluation_type": "repeated_group_shuffle_split",
        "splits": EVALUATION_SPLITS,
        "test_size": TEST_SIZE,
        "dataset_rows": len(dataset),
        "aircraft_classes": int(y.nunique()),
        "distinct_routes": int(groups.nunique()),
        "filtering": filtering,
        "summary": summary,
        "split_results": split_results,
        "limitations": [
            "Historical equipment labels are not flight frequencies.",
            "These splits reuse observations across repetitions.",
            "The model's class scores are not calibrated probabilities.",
            "Unseen aircraft classes cannot be predicted by the classifier.",
        ],
    }

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    (output_directory / "evaluation.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    write_csv(
        output_directory / "per_aircraft.csv",
        per_aircraft_rows,
        ["aircraft_icao", "support", "precision", "recall", "f1"],
    )

    write_csv(
        output_directory / "confusion.csv",
        confusion_rows,
        ["actual", "predicted", "count"],
    )

    write_csv(
        output_directory / "reliability.csv",
        reliability_rows,
        [
            "score_range",
            "count",
            "mean_model_score",
            "observed_accuracy",
        ],
    )

    logger.info(
        "ML EVALUATION COMPLETE | accuracy=%.4f | "
        "top3=%.4f | baseline=%.4f",
        summary["accuracy"]["mean"],
        summary["top_3_accuracy"]["mean"],
        summary["baseline_accuracy"]["mean"],
    )

    return report
