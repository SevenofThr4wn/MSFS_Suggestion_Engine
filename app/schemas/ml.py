from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class AircraftPredictionRequest(BaseModel):
    airline_icao: str = Field(min_length=2, max_length=4)
    departure_icao: str = Field(min_length=4, max_length=4)
    arrival_icao: str = Field(min_length=4, max_length=4)
    distance_nm: float = Field(gt=0, le=20000)

    @field_validator(
        "airline_icao",
        "departure_icao",
        "arrival_icao",
    )
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()


class AircraftPredictionCandidate(BaseModel):
    aircraft_icao: str
    model_score: float


class AircraftPredictionResponse(BaseModel):
    predicted_aircraft_icao: str
    model_version: str

    candidates: list[AircraftPredictionCandidate]

    reliability: str = "unknown"
    reliability_warnings: list[str] = Field(
        default_factory=list,
    )

    verified_assignment: bool = False

    warning: str = (
        "Statistical prediction based on historical data. "
        "Not evidence of a current airline aircraft assignment."
    )

class MLModelStatus(BaseModel):
    available: bool
    model_version: str | None = None
    trained_rows: int | None = None
    classes: list[str] = Field(default_factory=list)
    message: str | None = None


class AircraftFamilyCandidate(BaseModel):
    family_id: str
    family_name: str
    model_score: float


class AircraftFamilyPredictionResponse(BaseModel):
    predicted_family_id: str
    predicted_family_name: str

    model_version: str
    candidates: list[AircraftFamilyCandidate]

    reliability: str = "unknown"
    reliability_warnings: list[str] = Field(
        default_factory=list,
    )

    verified_assignment: bool = False

    warning: str = (
        "Aircraft-family prediction based on historical "
        "equipment records. Not a verified current assignment."
    )


from typing import Literal


class HybridAircraftSuggestion(BaseModel):
    aircraft_icao: str
    family_id: str | None = None
    family_name: str | None = None

    model_score: float
    matches_predicted_family: bool


class HybridAircraftPredictionResponse(BaseModel):
    predicted_family_id: str | None = None
    predicted_family_name: str | None = None

    predicted_aircraft_icao: str | None = None

    family_model_version: str | None = None
    variant_model_version: str | None = None

    model_agreement: Literal[
        "agree",
        "disagree",
        "unknown",
    ] = "unknown"

    reliability: Literal[
        "low",
        "moderate",
        "higher",
        "unknown",
    ] = "unknown"

    family_reliability: str = "unknown"
    variant_reliability: str = "unknown"

    suggested_variants: list[
        HybridAircraftSuggestion
    ] = Field(default_factory=list)

    family_candidates: list[
        AircraftFamilyCandidate
    ] = Field(default_factory=list)

    warnings: list[str] = Field(
        default_factory=list
    )

    verified_assignment: bool = False

    prediction_source: str = "historical_ml"

    disclaimer: str = (
        "Aircraft predictions are based on historical "
        "airline-route data. They do not verify current "
        "airline operations or scheduled aircraft."
    )
