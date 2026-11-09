
from typing import Literal

from pydantic import BaseModel, Field
from datetime import date

from app.schemas.route import (
    RouteRecommendation,
    RouteRecommendationRequest,
)

from app.schemas.schedule import ScheduleMatch

class AirportLocation(BaseModel):
    """Geographic and identifying information for an airport."""

    icao: str
    airport_name: str | None = None

    city: str | None = None
    region: str | None = None
    country: str | None = None

    display_name: str


class RecommendationRequest(RouteRecommendationRequest):
    """Additional configuration for generating flight recommendations."""

    strict_aircraft_category: bool = True
    require_real_world_service: bool = False

    min_flyability_score: float = Field(
        default=0,
        ge=0,
        le=100,
    )

    live_weather: bool = False
    weather_preference: Literal[
        "any",
        "fair",
        "challenging",
    ] = "any"

    scenarios_enabled: bool = False
    departure_gate_enabled: bool = True
    departure_date: date | None = None

    include_decision_trace: bool = False
    include_rejected_examples: bool = True

    schedule_enabled: bool = False
    require_scheduled_service: bool = False
    prefer_scheduled_aircraft: bool = True


class ScoredRecommendation(BaseModel):
    """A flight recommendation with scores and supporting information."""

    # Route information
    route: RouteRecommendation

    # Airport information
    arrival_location: AirportLocation | None = None

    # Airline operations and schedules
    schedule: ScheduleMatch | None = None
    scheduled_service_verified: bool = False

    # Recommendation scores
    flyability_score: float
    preference_score: float
    realism_score: float | None
    history_novelty_score: float
    weather_score: float | None
    final_score: float

    score_breakdown: dict[str, float]
    evidence_coverage: dict[str, bool]

    # Aircraft and airport validation
    aircraft_validation: dict = Field(default_factory=dict)
    departure_gate: dict = Field(default_factory=dict)

    # Supporting information
    realism: dict
    weather: dict
    scenario: dict

    # Explanations
    reasons: list[str]


class RecommendationResponse(BaseModel):
    """Complete response from the recommendation generation engine."""

    engine: str = "MSFS Recommendation Engine"
    request_id: str | None = None

    departure_location: AirportLocation | None = None

    generated_candidates: int
    evaluated_routes: int
    eligible_after_filters: int
    returned: int

    recommendations: list[ScoredRecommendation]

    warnings: list[str] = Field(
        default_factory=list,
    )

    decision_trace: dict | None = None
    rejected_examples: list[dict] = Field(
        default_factory=list,
    )
