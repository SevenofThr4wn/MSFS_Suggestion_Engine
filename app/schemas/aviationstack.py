from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class LiveFlightRequest(BaseModel):
    departure_icao: str = Field(min_length=4, max_length=4)
    arrival_icao: str = Field(min_length=4, max_length=4)
    limit: int = Field(default=20, ge=1, le=100)

    @field_validator("departure_icao", "arrival_icao")
    @classmethod
    def normalize_icao(cls, value: str) -> str:
        return value.strip().upper()


class LiveFlight(BaseModel):
    flight_number: str | None = None
    flight_icao: str | None = None
    airline_name: str | None = None
    airline_iata: str | None = None
    airline_icao: str | None = None

    departure_icao: str
    arrival_icao: str

    flight_date: str | None = None
    flight_status: str | None = None

    departure_scheduled: datetime | None = None
    arrival_scheduled: datetime | None = None

    aircraft_icao: str | None = None
    aircraft_registration: str | None = None

    source: str = "aviationstack"


class LiveFlightResponse(BaseModel):
    departure_icao: str
    arrival_icao: str

    status: Literal[
        "available",
        "no_observations",
        "unavailable",
        "disabled",
    ]

    flights: list[LiveFlight] = Field(default_factory=list)

    cached: bool = False
    source: str = "aviationstack"

    # These observations do not verify future service.
    future_schedule_verified: bool = False

    message: str | None = None
