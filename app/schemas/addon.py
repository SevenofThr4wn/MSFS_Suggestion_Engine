from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class AddonCategory(StrEnum):
    AIRCRAFT = "aircraft"
    LIVERY = "livery"
    AIRPORT = "airport"
    SCENERY = "scenery"
    TRAFFIC = "traffic"
    UTILITY = "utility"
    UNKNOWN = "unknown"


class DetectionMethod(StrEnum):
    MANIFEST = "manifest"
    FOLDER_NAME = "folder_name"


class AddonPackage(BaseModel):
    package_id: str
    name: str
    category: AddonCategory
    content_type: str | None = None
    version: str | None = None
    creator: str | None = None

    source: str
    detection_method: DetectionMethod

    installed: bool = True
    enabled: bool | None = None

    aircraft_icao: str | None = None
    airport_icao: str | None = None
    airline_icao: str | None = None


class AddonScanRoot(BaseModel):
    label: str
    available: bool
    packages_found: int = 0


class AddonInventoryResponse(BaseModel):
    scanned_at: datetime
    total_packages: int
    cached: bool = False

    categories: dict[str, int] = Field(default_factory=dict)
    roots: list[AddonScanRoot] = Field(default_factory=list)
    packages: list[AddonPackage] = Field(default_factory=list)

    aircraft_variants: list[AircraftVariant] = Field(default_factory=list)
    airport_candidates: list[AirportCandidate] = Field(default_factory=list)
    utilities: list[UtilityComponent] = Field(default_factory=list)

    warnings: list[str] = Field(default_factory=list)


class AircraftVariant(BaseModel):
    package_id: str
    title: str
    aircraft_icao: str | None = None
    airline_icao: str | None = None
    airline_name: str | None = None
    registration: str | None = None
    user_selectable: bool | None = None
    is_livery: bool = False


class AirportCandidate(BaseModel):
    package_id: str
    icao: str
    evidence: str
    verified: bool = False


class UtilityComponent(BaseModel):
    name: str
    component: str
    detected: bool
    evidence: str
