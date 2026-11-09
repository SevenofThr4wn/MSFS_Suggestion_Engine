from pydantic import BaseModel, ConfigDict, Field

from app.schemas.aircraft import AircraftCheck, AircraftEvaluationResult


class RunwayResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    designation: str
    length_m: float
    width_m: float | None = None
    surface: str | None = None


class AirportResponse(BaseModel):
    id: int
    icao_code: str
    iata_code: str | None
    name: str
    city: str | None
    country: str | None
    latitude: float
    longitude: float
    elevation_ft: int | None
    timezone: str | None
    has_ils: bool | None
    has_addon_scenery: bool
    scenery_developer: str | None
    runways: list[RunwayResponse]


class AirportSearchResponse(BaseModel):
    total: int
    airports: list[AirportResponse]


class RunwayAssessment(BaseModel):
    runway_id: int
    designation: str
    length_m: float
    surface: str | None
    check: AircraftCheck


class AirportCompatibilityResponse(BaseModel):
    airport: AirportResponse
    aircraft_id: int
    aircraft_name: str
    operation: str
    suitability: str
    assessments: list[RunwayAssessment]
    selected_runway: RunwayAssessment | None = None
    warnings: list[str] = Field(default_factory=list)


class FlightAirportCompatibilityResponse(BaseModel):
    departure: AirportCompatibilityResponse
    arrival: AirportCompatibilityResponse
    route_distance_nm: float
    aircraft_evaluation: AircraftEvaluationResult
    overall_suitability: str
    warnings: list[str] = Field(default_factory=list)
