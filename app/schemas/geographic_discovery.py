from pydantic import BaseModel, Field


class GeographicDiscoveryRequest(BaseModel):
    departure_code: str = Field(min_length=3, max_length=8)

    min_distance_nm: float = Field(default=100, ge=0)
    max_distance_nm: float = Field(default=3000, gt=0)

    limit: int = Field(default=100, ge=1, le=20000)


class GeographicCandidate(BaseModel):
    icao_code: str
    iata_code: str | None
    name: str

    distance_nm: float
    initial_bearing_deg: float


class GeographicDiscoveryResponse(BaseModel):
    departure_code: str
    total_matches: int
    candidates: list[GeographicCandidate]
