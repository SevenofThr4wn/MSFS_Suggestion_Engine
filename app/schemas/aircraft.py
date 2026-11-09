from enum import StrEnum
from pydantic import BaseModel, Field, model_validator


class CheckStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"
    SKIPPED = "skipped"


class AircraftEvaluationRequest(BaseModel):
    route_distance_nm: float = Field(gt=0)
    distance_margin: float = Field(
        default=0.10,
        ge=0,
        le=1,
    )

    departure_runway_m: float | None = Field(
        default=None,
        gt=0,
    )

    arrival_runway_m: float | None = Field(
        default=None,
        gt=0,
    )

    preferred_category: str | None = None
    preferred_icao_code: str | None = None
    owned_only: bool = False

    suitable_only: bool = False

    limit: int = Field(default=10, ge=1, le=100)

    @model_validator(mode="after")
    def normalize_preferences(self):
        if self.preferred_category:
            self.preferred_category = (
                self.preferred_category.strip().lower()
            )

        if self.preferred_icao_code:
            self.preferred_icao_code = (
                self.preferred_icao_code.strip().upper()
            )

        return self


class AircraftCheck(BaseModel):
    status: CheckStatus
    explanation: str

    required_value: float | None = None
    available_value: float | None = None

    unit: str | None = None


class AircraftEvaluationResult(BaseModel):
    aircraft_id: int
    aircraft_name: str
    icao_code: str | None
    category: str
    is_owned: bool

    range_check: AircraftCheck
    takeoff_check: AircraftCheck
    landing_check: AircraftCheck

    suitability: str
    score: float = Field(ge=0, le=100)

    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AircraftRecommendationResponse(BaseModel):
    total_evaluated: int
    total_returned: int
    recommendations: list[AircraftEvaluationResult]

class AircraftDetailResponse(BaseModel):
    """Detailed information about an aircraft."""

    id: int = Field(
        ...,
        description="Unique database identifier of the aircraft.",
        examples=[1],
    )

    name: str = Field(
        ...,
        description="Display name of the aircraft.",
        examples=["Airbus A380-800"],
    )

    icao_code: str | None = Field(
        default=None,
        description="ICAO aircraft type designator.",
        examples=["A388"],
    )

    category: str | None = Field(
        default=None,
        description="Classification or category of the aircraft.",
        examples=["wide_body"],
    )

    range_nm: float | None = Field(
        default=None,
        description="Maximum aircraft range in nautical miles.",
    )

    cruise_speed_kts: float | None = Field(
        default=None,
        description="Aircraft cruise speed in knots.",
    )

    takeoff_distance_m: float | None = Field(
        default=None,
        description="Required takeoff distance in metres.",
    )

    landing_distance_m: float | None = Field(
        default=None,
        description="Required landing distance in metres.",
    )

    is_owned: bool = Field(
        ...,
        description=(
            "Indicates whether the aircraft is owned "
            "by the user in the simulator."
        ),
        examples=[True],
    )