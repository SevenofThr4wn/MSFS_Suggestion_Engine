from __future__ import annotations

import math
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_airport_catalog
from app.db.repositories.airport_preferences_repository import AirportPreferencesRepository
from app.db.session import get_db
from app.providers.airport_catalog import AirportCatalog

router = APIRouter(prefix="/route-finder", tags=["Route Finder"])

@router.get("/scenery")
def get_installed_scenery_network(
    db: Annotated[Session, Depends(get_db)],
    catalog: Annotated[AirportCatalog, Depends(get_airport_catalog)]
) -> dict:

    codes = sorted(AirportPreferencesRepository(db).list_addon_codes())
    airports: list[dict] = []
    missing: list[str] = []

    for code in codes:
        airport = catalog.get_by_code(code)

        if airport is None:
            missing.append(code)
            continue

        lat, lon = airport.latitude, airport.longitude

        if (
            lat is None or lon is None
            or not math.isfinite(lat) or not math.isfinite(lon)
            or not -90 <= lat <= 90 or not -180 <= lon <= 180
        ):
            missing.append(code)
            continue

        airports.append({
            "icao": airport.icao_code,
            "name": airport.name,
            "city": airport.city,
            "country": airport.country,
            "latitude": lat,
            "longitude": lon
        })

    return {
        "source": "installed_scenery_preferences",
        "airports": airports,
        "missing": missing,
        "connections_are_verified_routes": False
    }