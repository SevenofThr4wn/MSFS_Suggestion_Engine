from __future__ import annotations

import pandas as pd

from app.schemas.ml import AircraftPredictionRequest


FEATURE_COLUMNS = [
    "airline_icao",
    "departure_icao",
    "arrival_icao",
    "distance_nm",
]

CATEGORICAL_COLUMNS = [
    "airline_icao",
    "departure_icao",
    "arrival_icao",
]

NUMERIC_COLUMNS = ["distance_nm"]

TARGET_COLUMN = "aircraft_icao"


def prepare_features(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """Normalize features consistently for training and inference."""
    result = dataframe[FEATURE_COLUMNS].copy()

    for column in CATEGORICAL_COLUMNS:
        result[column] = (
            result[column]
            .astype("string")
            .str.strip()
            .str.upper()
            .fillna("UNKNOWN")
        )

    result["distance_nm"] = pd.to_numeric(
        result["distance_nm"],
        errors="raise",
    ).astype(float)

    if result["distance_nm"].isna().any():
        raise ValueError("Distance contains missing values.")

    if not result["distance_nm"].between(0, 20000).all():
        raise ValueError("Distance is outside supported bounds.")

    return result


def prediction_features(
    request: AircraftPredictionRequest,
) -> pd.DataFrame:
    """Convert an API prediction request to model features."""
    return prepare_features(
        pd.DataFrame(
            [
                {
                    "airline_icao": request.airline_icao,
                    "departure_icao": request.departure_icao,
                    "arrival_icao": request.arrival_icao,
                    "distance_nm": request.distance_nm,
                }
            ]
        )
    )
