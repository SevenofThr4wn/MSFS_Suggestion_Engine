from __future__ import annotations

import math
import re
from typing import Final

import pandas as pd

from app.schemas.ml import AircraftPredictionRequest


# ============================================================
# Feature Configuration
# ============================================================

FEATURE_COLUMNS: Final[tuple[str, ...]] = (
    "airline_icao",
    "departure_icao",
    "arrival_icao",
    "distance_nm",
)

CATEGORICAL_COLUMNS: Final[tuple[str, ...]] = (
    "airline_icao",
    "departure_icao",
    "arrival_icao",
)

NUMERIC_COLUMNS: Final[tuple[str, ...]] = (
    "distance_nm",
)

TARGET_COLUMN: Final[str] = "aircraft_icao"

MAX_DISTANCE_NM: Final[float] = 20_000.0

AIRLINE_PATTERN: Final = re.compile(
    r"^[A-Z0-9]{2,4}$"
)

AIRPORT_PATTERN: Final = re.compile(
    r"^[A-Z]{4}$"
)


# ============================================================
# Validation
# ============================================================

def validate_feature_columns(
    dataframe: pd.DataFrame,
) -> None:
    """Ensure all required model features are present."""

    missing = set(FEATURE_COLUMNS) - set(
        dataframe.columns
    )

    if missing:
        raise ValueError(
            "Missing ML feature columns: "
            f"{sorted(missing)}"
        )

    if dataframe.empty:
        raise ValueError(
            "ML feature dataframe cannot be empty."
        )


def normalize_categorical(
    series: pd.Series,
    column: str,
) -> pd.Series:
    """Normalize and validate categorical identifiers."""

    result = (
        series.astype("string")
        .str.strip()
        .str.upper()
    )

    missing = (
        result.isna()
        | result.eq("").fillna(False)
    )

    if missing.any():
        raise ValueError(
            f"Feature '{column}' contains missing values."
        )

    pattern = (
        AIRLINE_PATTERN
        if column == "airline_icao"
        else AIRPORT_PATTERN
    )

    valid = result.str.fullmatch(
        pattern.pattern
    ).fillna(False)

    if not valid.all():
        invalid = (
            result.loc[~valid]
            .drop_duplicates()
            .head(5)
            .tolist()
        )

        raise ValueError(
            f"Feature '{column}' contains invalid "
            f"identifiers: {invalid}"
        )

    return result.astype(str)


def normalize_distance(
    series: pd.Series,
) -> pd.Series:
    """Validate route distance in nautical miles."""

    result = pd.to_numeric(
        series,
        errors="coerce",
    )

    if result.isna().any():
        raise ValueError(
            "Route distance contains missing "
            "or non-numeric values."
        )

    values = result.to_numpy(dtype=float)

    if not all(math.isfinite(v) for v in values):
        raise ValueError(
            "Route distance must be finite."
        )

    if not (
        (values > 0)
        & (values <= MAX_DISTANCE_NM)
    ).all():
        raise ValueError(
            "Route distance must be greater than "
            f"0 and at most {MAX_DISTANCE_NM:,.0f} NM."
        )

    return result.astype(float)


# ============================================================
# Training / Inference Features
# ============================================================

def prepare_features(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Prepare consistent features for training and inference.

    Parameters
    ----------
    dataframe : pd.DataFrame
        Raw feature data containing airline, departure,
        arrival and route distance.

    Returns
    -------
    pd.DataFrame
        Normalized features in the exact order required
        by the trained ML pipelines.

    Raises
    ------
    ValueError
        If required columns are missing, identifiers are
        invalid or distances are outside supported bounds.

    Notes
    -----
    Feature ordering is intentionally preserved for
    compatibility with existing V1 and V2 model artifacts.
    """

    validate_feature_columns(dataframe)

    result = dataframe.loc[
        :, list(FEATURE_COLUMNS)
    ].copy()

    for column in CATEGORICAL_COLUMNS:
        result[column] = normalize_categorical(
            result[column],
            column,
        )

    result["distance_nm"] = normalize_distance(
        result["distance_nm"]
    )

    return result


def prediction_features(
    request: AircraftPredictionRequest,
) -> pd.DataFrame:
    """
    Convert an aircraft prediction request into model input.

    This function uses the same normalization pipeline
    as model training, preventing differences between
    training and inference feature representations.
    """

    dataframe = pd.DataFrame(
        [
            {
                "airline_icao": request.airline_icao,
                "departure_icao": request.departure_icao,
                "arrival_icao": request.arrival_icao,
                "distance_nm": request.distance_nm,
            }
        ]
    )

    return prepare_features(dataframe)
