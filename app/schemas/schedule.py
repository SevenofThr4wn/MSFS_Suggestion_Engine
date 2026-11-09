from __future__ import annotations

from datetime import date, datetime, time
from enum import StrEnum

from pydantic import BaseModel, Field


class ScheduleStatus(StrEnum):
    VERIFIED = "verified"
    HISTORICAL = "historical"
    UNVERIFIED = "unverified"
    UNKNOWN = "unknown"


class ServiceType(StrEnum):
    PASSENGER = "passenger"
    CARGO = "cargo"
    CHARTER = "charter"
    OTHER = "other"
    UNKNOWN = "unknown"


class AircraftMatch(StrEnum):
    EXACT = "exact"
    FAMILY = "family"
    MISMATCH = "mismatch"
    UNKNOWN = "unknown"


class FlightSchedule(BaseModel):
    airline_name: str
    airline_iata: str | None = None
    airline_icao: str | None = None

    flight_number: str | None = None
    callsign: str | None = None

    departure_icao: str
    arrival_icao: str

    departure_time_local: time | None = None
    arrival_time_local: time | None = None
    arrival_day_offset: int | None = None

    aircraft_icao: str | None = None
    aircraft_name: str | None = None

    service_type: ServiceType = ServiceType.UNKNOWN

    operating_days: list[int] = Field(
        default_factory=list,
        description="ISO weekdays: Monday=1, Sunday=7",
    )

    valid_from: date | None = None
    valid_until: date | None = None

    source: str | None = None
    source_reference: str | None = None
    last_verified: datetime | None = None

    status: ScheduleStatus = ScheduleStatus.UNKNOWN


class ScheduleLookupRequest(BaseModel):
    departure_icao: str = Field(
        min_length=4,
        max_length=4,
    )
    arrival_icao: str = Field(
        min_length=4,
        max_length=4,
    )

    departure_date: date | None = None
    aircraft_icao: str | None = None
    airline_icao: str | None = None


class ScheduleMatch(BaseModel):
    schedule: FlightSchedule
    aircraft_match: AircraftMatch
    operates_on_date: bool | None = None
    reasons: list[str] = Field(default_factory=list)


class ScheduleLookupResponse(BaseModel):
    departure_icao: str
    arrival_icao: str
    departure_date: date | None = None

    status: ScheduleStatus
    matches: list[ScheduleMatch] = Field(
        default_factory=list,
    )

    warnings: list[str] = Field(default_factory=list)
