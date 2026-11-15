from dataclasses import dataclass

from app.db.models.aircraft import Aircraft
from app.db.models.route_catalog import RouteCatalogEntry
from app.providers.airport_catalog import AirportRecord


@dataclass(frozen=True)
class RouteCandidate:
    departure: AirportRecord
    arrival: AirportRecord
    aircraft: Aircraft
    route: RouteCatalogEntry | None = None

@dataclass(frozen=True)
class DurationEstimate:
    """Estimated flight and block time for a route."""

    air_time_min: int
    block_time_min: int
    cruise_distance_nm: float
    source: str = "simplified_aircraft_performance"