from typing import Literal
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

class AirportMode(StrEnum):
    ALL = "all"
    COMMERCIAL = "commercial"
    MAJOR = "major"
    MAIN_HUBS = "main_hubs"


class AirportFilterOptions(BaseModel):
    minimum_airport_size: Literal[
        "small_airport",
        "medium_airport",
        "large_airport",
    ] | None = None

    require_paved_runway: bool | None = None
    require_known_runway_data: bool = False
    require_scheduled_service: bool = False

class RouteMode(StrEnum):
    DATABASE = "database"
    DISCOVERY = "discovery"


class RouteStatus(StrEnum):
    PRELIMINARY_PASS = "preliminary_pass"
    INDETERMINATE = "indeterminate"
    REJECTED = "rejected"


class RouteRecommendationRequest(BaseModel):
    mode: RouteMode = RouteMode.DISCOVERY

    # Airport preferences
    departure_code: str | None = None
    arrival_code: str | None = None
    prefer_addon_scenery: bool = True

    # Aircraft preferences
    aircraft_id: int | None = Field(default=None, gt=0)
    preferred_category: str | None = None
    owned_only: bool = True

    # Duration constraints, in hours
    min_duration_hours: float = Field(
        default=1.0, ge=0, le=30
    )
    max_duration_hours: float = Field(
        default=8.0, gt=0, le=30
    )

    # Candidate generation
    max_airports: int = Field(default=100, ge=2, le=500)
    max_candidates: int = Field(
        default=5000, ge=1, le=20000
    )

    # Recommendation settings
    include_indeterminate: bool = False
    require_real_world_route: bool = False
    limit: int = Field(default=10, ge=1, le=50)

    airport_filter: AirportFilterOptions = Field(
    default_factory=AirportFilterOptions
    )

    airport_mode: AirportMode = AirportMode.MAJOR

    min_flyability_score: float = Field(
        default=0,
        ge=0,
        le=100,
    )

    @model_validator(mode="after")
    def validate_request(self):
        if self.min_duration_hours > self.max_duration_hours:
            raise ValueError(
                "Minimum duration cannot exceed maximum duration."
            )

        for field in ("departure_code", "arrival_code"):
            value = getattr(self, field)
            if value:
                setattr(self, field, value.strip().upper())

        if self.preferred_category:
            self.preferred_category = (
                self.preferred_category.strip().lower()
            )

        if (
            self.mode == RouteMode.DISCOVERY
            and self.require_real_world_route
        ):
            raise ValueError(
                "Real-world route verification requires database mode."
            )

        return self


class RouteRecommendation(BaseModel):
    route_id: int | None = None

    departure_icao: str
    departure_name: str

    arrival_icao: str
    arrival_name: str

    aircraft_id: int
    aircraft_name: str
    aircraft_icao_code: str | None = None

    registration: str | None = None
    registration_verified: bool = False

    airline_name: str | None = None
    airline_icao: str | None = None
    flight_number: str | None = None

    is_real_world_route: bool

    distance_nm: float
    distance_source: str

    estimated_duration_min: int
    duration_source: str

    suitability: RouteStatus
    score: float = Field(ge=0, le=100)

    score_breakdown: dict[str, float] = Field(
        default_factory=dict
    )

    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    flyability_score: float = Field(
        ge=0,
        le=100,
        description=(
            "Estimated enjoyment and willingness to repeat "
            "this flight. Not a safety or suitability score."
        )
    )

    flyability_status: Literal[
        "estimated",
        "personalized",
    ] = "estimated"

    flyability_breakdown: dict[str, float] = Field(
        default_factory=dict,
    )

    flyability_evidence: dict[str, bool] = Field(
        default_factory=dict
    )

    personal_feedback_available: bool = False


class RouteRecommendationResponse(BaseModel):
    mode: RouteMode
    total_candidates: int
    total_validated: int
    total_eligible: int
    returned: int
    recommendations: list[RouteRecommendation]
