from dataclasses import asdict, dataclass, field
from typing import Any, List, Optional

from app.core.classes.validation import Suitability
from app.core.enums import SuitabilityStatus
from app.providers.airport_catalog import AirportRecord
from app.providers.runway_provider import RunwayData
from app.schemas.aircraft import AircraftCheck


@dataclass(frozen=True)
class SuitabilityProfile:
    minimum_airport_size: str | None
    minimum_runway_length_m: float
    minimum_runway_width_m: float
    require_paved_runway: bool = True


@dataclass
class StandInfo:
    name: str
    latitude: float
    longitude: float
    heading: float = 0.0
    radius_m: float = 18.0
    wingspan_m: float = 36.0
    terminal: str = ""
    airlines: List[str] = field(default_factory=list)
    has_jetway: bool = False
    is_cargo: bool = False
    is_ga: bool = False
    is_military: bool = False
    is_schengen: Optional[bool] = None
    occupied: bool = False
    mars_group: Optional[str] = None


@dataclass(frozen=True)
class GateSuggestion:
    airport_icao: str
    gate: str | None
    status: str
    source: str
    reasons: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class AirportSuitabilityResult:
    airport_icao: str
    aircraft_id: int
    operation: str
    status: SuitabilityStatus
    selected_runway: RunwayData | None
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class RunwayAssessment:
    runway: RunwayData
    check: AircraftCheck

@dataclass(frozen=True)
class AirportAssessment:
    airport: AirportRecord
    operation: str
    suitability: Suitability
    selected_runway: RunwayAssessment | None
    assessments: list[RunwayAssessment]
    warnings: list[str]


@dataclass(frozen=True)
class _IndexedAirport:
    icao_code: str
    iata_code: str | None
    name: str
    latitude: float
    longitude: float
    distance_nm: float


@dataclass(frozen=True)
class _OriginIndex:
    provider: Any
    latitude: float
    longitude: float
    created_at: float
    distances: tuple[float, ...]
    airports: tuple[_IndexedAirport, ...]


@dataclass
class StandInfo:
    name: str
    latitude: float
    longitude: float
    heading: float = 0.0
    radius_m: float = 18.0
    wingspan_m: float = 36.0
    terminal: str = ""
    airlines: List[str] = field(default_factory=list)
    has_jetway: bool = False
    is_cargo: bool = False
    is_ga: bool = False
    is_military: bool = False
    is_schengen: Optional[bool] = None
    occupied: bool = False
    mars_group: Optional[str] = None