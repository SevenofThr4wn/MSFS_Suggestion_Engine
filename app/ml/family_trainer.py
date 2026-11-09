
from __future__ import annotations

from pathlib import Path

from app.core.logging import get_logger
from app.ml.aircraft_families import validate_family_mapping
from app.ml.trainer_v2 import (
    load_data,
    train_model,
)


logger = get_logger("ml.family_trainer")

MODEL_VERSION = "flightengine-ml-v2-family"

DEFAULT_DATASET_PATH = Path(
    "data/ml/aircraft_assignments_v2.csv"
)

DEFAULT_DETAILED_PATH = Path(
    "data/ml/bts_assignments_detailed.csv"
)

DEFAULT_OUTPUT_PATH = Path(
    "models/v2/aircraft_family.joblib"
)


def train_family_model(
    dataset_path: Path = DEFAULT_DATASET_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    detailed_path: Path = DEFAULT_DETAILED_PATH,
) -> dict:
    """
    Train the FlightEngine V2 aircraft-family classifier.

    Uses the shared V2 training implementation to ensure
    that aircraft-family and aircraft-type classifiers
    follow consistent training and evaluation policies.

    Parameters
    ----------
    dataset_path : Path
        Combined historical and BTS training dataset.

    output_path : Path
        Destination for the trained family model artifact.

    detailed_path : Path
        Monthly BTS observations, including departure
        counts and observation dates.

    Returns
    -------
    dict
        Chronological evaluation metrics, including
        top-1, top-3 and departure-weighted accuracy.

    Raises
    ------
    FileNotFoundError
        If a required training dataset is missing.

    ValueError
        If training data is invalid, has insufficient
        target diversity or lacks enough time periods.

    Notes
    -----
    The model is trained in two stages:

    1. Chronological evaluation using earlier BTS
       observations for training and later months
       for testing.

    2. Production training using all available
       observations after evaluation.

    Predictions are statistical estimates and do not
    verify current airline aircraft assignments.
    """

    dataset_path = Path(dataset_path).expanduser()
    detailed_path = Path(detailed_path).expanduser()
    output_path = Path(output_path).expanduser()

    validate_family_mapping()

    if not dataset_path.is_file():
        raise FileNotFoundError(
            "Combined ML dataset not found: "
            f"{dataset_path}"
        )

    if not detailed_path.is_file():
        raise FileNotFoundError(
            "Detailed BTS dataset not found: "
            f"{detailed_path}"
        )

    # Avoid accidentally overwriting the original
    # family model when using older training scripts.
    legacy_output = Path(
        "models/aircraft_family.joblib"
    ).resolve()

    if output_path.resolve() == legacy_output:
        raise ValueError(
            "Refusing to overwrite the legacy family model. "
            "Use models/v2/aircraft_family.joblib instead."
        )

    logger.info(
        "FAMILY V2 TRAINING STARTED | "
        "combined=%s | detailed=%s | output=%s",
        dataset_path,
        detailed_path,
        output_path,
    )

    historical, detailed = load_data(
        combined_path=dataset_path,
        detailed_path=detailed_path,
    )

    evaluation = train_model(
        historical=historical,
        detailed=detailed,
        mode="family",
        output=output_path,
    )

    logger.info(
        "FAMILY V2 TRAINING COMPLETE | "
        "accuracy=%.4f | top3=%.4f | "
        "weighted_accuracy=%.4f | "
        "weighted_top3=%.4f",
        evaluation["accuracy"],
        evaluation["top_3_accuracy"],
        evaluation["departure_weighted_accuracy"],
        evaluation["departure_weighted_top_3"],
    )

    return evaluation
