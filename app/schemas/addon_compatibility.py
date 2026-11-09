
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class CompatibilityStatus(StrEnum):
    DETECTED = "detected"
    NOT_DETECTED = "not_detected"
    UNKNOWN = "unknown"


class CompatibilityCheck(BaseModel):
    status: CompatibilityStatus
    package_ids: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    explanation: str


class AddonCompatibilityRequest(BaseModel):
    aircraft_icao: str | None = None
    airline_icao: str | None = None

    departure_icao: str
    arrival_icao: str

    @field_validator(
        "aircraft_icao",
        "airline_icao",
        "departure_icao",
        "arrival_icao",
    )
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        if value is None:
            return None

        return value.strip().upper()


class AddonCompatibilityResponse(BaseModel):
    aircraft: CompatibilityCheck
    livery: CompatibilityCheck

    departure_scenery: CompatibilityCheck
    arrival_scenery: CompatibilityCheck

    gsx: CompatibilityCheck
    fsltl: CompatibilityCheck

    inventory_scanned_at: str
    warnings: list[str] = Field(default_factory=list)
