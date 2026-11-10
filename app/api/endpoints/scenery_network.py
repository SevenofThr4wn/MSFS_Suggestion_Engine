
from __future__ import annotations

import math
import re
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_airport_catalog
from app.api.endpoints.addons import get_addon_inventory_service
from app.providers.airport_catalog import AirportCatalog
from app.schemas.addon import AddonCategory
from app.services.addon_inventory_service import AddonInventoryService


from fastapi import Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.repositories.route_catalog_repository import (
    RouteCatalogRepository,
)
from app.engines.scenery_network_engine import (
    SceneryNetworkEngine,
)



router = APIRouter(
    prefix="/route-finder",
    tags=["Route Finder"],
)



@router.get("/scenery")
def get_installed_scenery_network(
    catalog: Annotated[
        AirportCatalog,
        Depends(get_airport_catalog),
    ],
    service: Annotated[
        AddonInventoryService,
        Depends(get_addon_inventory_service),
    ],
    db: Annotated[
        Session,
        Depends(get_db),
    ],
    refresh: bool = False,
    include_plausible: bool = False,
    owned_only: bool = True,
    max_distance_nm: Annotated[
        float,
        Query(ge=100, le=11000),
    ] = 10000,
) -> dict:

    """Return airports detected from installed MSFS packages."""

    inventory = service.scan(refresh=refresh)

    packages = {
        package.package_id.casefold(): package
        for package in inventory.packages
        if package.installed
        and package.enabled is not False
        and package.category in {
            AddonCategory.AIRPORT,
            AddonCategory.SCENERY,
        }
    }

    airports: list[dict] = []
    missing: list[str] = []
    seen: set[str] = set()

    for candidate in inventory.airport_candidates:
        code = candidate.icao.strip().upper()

        if not re.fullmatch(r"[A-Z]{4}", code):
            continue

        if code in seen:
            continue

        if candidate.package_id.casefold() not in packages:
            continue

        airport = catalog.get_by_code(code)

        if airport is None:
            missing.append(code)
            continue

        lat = airport.latitude
        lon = airport.longitude

        if (
            lat is None
            or lon is None
            or not math.isfinite(lat)
            or not math.isfinite(lon)
            or not -90 <= lat <= 90
            or not -180 <= lon <= 180
        ):
            missing.append(code)
            continue

        seen.add(code)

        airports.append({
            "icao": code,
            "name": airport.name,
            "city": airport.city,
            "country": airport.country,
            "latitude": lat,
            "longitude": lon,
        })

    airports.sort(key=lambda airport: airport["icao"])

    
    engine = SceneryNetworkEngine(
        repository=RouteCatalogRepository(db),
        airport_catalog=catalog,
    )

    connections = engine.generate(
        installed_codes={
            airport["icao"] for airport in airports
        },
        include_plausible=include_plausible,
        owned_only=owned_only,
        max_distance_nm=max_distance_nm,
    )

    return {
        "source": "installed_addon_inventory",
        "airports": airports,
        "missing": sorted(set(missing)),
        "connections": connections,
        "connections_are_verified_routes": (
            not include_plausible
        ),
        "filters": {
            "include_plausible": include_plausible,
            "owned_only": owned_only,
            "max_distance_nm": max_distance_nm,
        },
    }

