from dataclasses import dataclass

from app.db.repositories.aircraft_repository import (
    AircraftRepository,
)
from app.engines.aircraft_engine import AircraftEngine
from app.engines.airport_engine import (
    AirportAssessment,
    AirportEngine,
)
from app.engines.geographic_engine import GeographicEngine
from app.providers.airport_catalog import AirportCatalog
from app.schemas.aircraft import (
    AircraftEvaluationRequest,
    AircraftEvaluationResult,
)


@dataclass(frozen=True)
class FlightCompatibility:
    departure: AirportAssessment
    arrival: AirportAssessment
    aircraft_evaluation: AircraftEvaluationResult
    route_distance_nm: float
    overall_suitability: str
    warnings: list[str]


class CompatibilityService:
    def __init__(
        self,
        airport_catalog: AirportCatalog,
        aircraft_repository: AircraftRepository,
    ):
        self.catalog = airport_catalog
        self.aircraft_repository = aircraft_repository
        self.airport_engine = AirportEngine()
        self.aircraft_engine = AircraftEngine(
            aircraft_repository
        )

    def evaluate_flight(
        self,
        aircraft_id: int,
        departure_code: str,
        arrival_code: str,
        distance_margin: float = 0.10,
        route_distance_nm: float | None = None,
    ) -> FlightCompatibility:

        aircraft = self.aircraft_repository.get_by_id(
            aircraft_id
        )

        if aircraft is None:
            raise LookupError("Aircraft not found.")

        departure = self.catalog.get_by_code(
            departure_code
        )
        arrival = self.catalog.get_by_code(
            arrival_code
        )

        if departure is None:
            raise LookupError("Departure airport not found.")

        if arrival is None:
            raise LookupError("Arrival airport not found.")

        if departure.icao_code == arrival.icao_code:
            raise ValueError(
                "Departure and arrival airports must differ."
            )

        distance = (
            route_distance_nm
            if route_distance_nm is not None
            else GeographicEngine.distance_nm(
                departure.latitude,
                departure.longitude,
                arrival.latitude,
                arrival.longitude,
            )
        )

        if distance <= 0:
            raise ValueError("Route distance must be positive.")

        dep_result = self.airport_engine.evaluate(
            departure, aircraft, "takeoff"
        )

        arr_result = self.airport_engine.evaluate(
            arrival, aircraft, "landing"
        )

        aircraft_result = (
            self.aircraft_engine.evaluate_aircraft(
                aircraft,
                AircraftEvaluationRequest(
                    route_distance_nm=distance,
                    distance_margin=distance_margin,
                    departure_runway_m=(
                        dep_result.selected_runway.runway.length_m
                        if dep_result.selected_runway
                        else None
                    ),
                    arrival_runway_m=(
                        arr_result.selected_runway.runway.length_m
                        if arr_result.selected_runway
                        else None
                    ),
                ),
            )
        )

        states = {
            dep_result.suitability,
            arr_result.suitability,
            aircraft_result.suitability,
        }

        if "rejected" in states:
            overall = "rejected"
        elif "indeterminate" in states:
            overall = "indeterminate"
        else:
            overall = "preliminary_pass"

        return FlightCompatibility(
            departure=dep_result,
            arrival=arr_result,
            aircraft_evaluation=aircraft_result,
            route_distance_nm=round(distance, 2),
            overall_suitability=overall,
            warnings=[
                "Aircraft and airport checks are preliminary.",
                "Great-circle distance is used when no "
                "route distance is provided.",
            ],
        )
