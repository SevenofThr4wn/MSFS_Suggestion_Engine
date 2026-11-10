from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.schemas.addon import AddonInventoryResponse
from app.schemas.addon_compatibility import AddonCompatibilityRequest, AddonCompatibilityResponse
from app.services.addon_compatibility_service import AddonCompatibilityService
from app.services.addon_inventory_service import (
    AddonInventoryService,
)

from itertools import combinations
import re

from app.api.dependencies import get_airport_catalog
from app.providers.airport_catalog import AirportCatalog
from app.schemas.addon import AddonCategory


router = APIRouter(
    prefix="/addons",
    tags=["Installed Add-ons"],
)


@lru_cache(maxsize=1)
def get_addon_inventory_service() -> AddonInventoryService:
    return AddonInventoryService(cache_seconds=300)


@router.get(
    "/inventory",
    response_model=AddonInventoryResponse,
    summary="Get Installed Add-ons",
)
def get_addon_inventory(
    service: Annotated[
        AddonInventoryService,
        Depends(get_addon_inventory_service),
    ],
    refresh: Annotated[
        bool,
        Query(description="Bypass the cached inventory."),
    ] = False,
) -> AddonInventoryResponse:
    return service.scan(refresh=refresh)


@router.post(
    "/compatibility",
    response_model=AddonCompatibilityResponse,
    summary="Check Flight Add-on Compatibility",
)
def check_addon_compatibility(
    request: AddonCompatibilityRequest,
    service: Annotated[
        AddonInventoryService,
        Depends(get_addon_inventory_service),
    ],
) -> AddonCompatibilityResponse:
    inventory = service.scan()

    compatibility = AddonCompatibilityService(
        inventory=inventory,
    )

    return compatibility.evaluate(request)

@router.get("/airports/network")
def get_installed_airport_network(
    service: Annotated[
        AddonInventoryService,
        Depends(get_addon_inventory_service),
    ],
    catalog: Annotated[
        AirportCatalog,
        Depends(get_airport_catalog),
    ],
    refresh: bool = False,
):
    """Return airport connections from installed MSFS add-ons only."""

    inventory = service.scan(refresh=refresh)

    installed_packages = {
        package.package_id.casefold(): package
        for package in inventory.packages
        if package.installed
        and package.enabled is not False
        and package.category in {
            AddonCategory.AIRPORT,
            AddonCategory.SCENERY,
        }
    }

    airports = {}

    for candidate in inventory.airport_candidates:
        package = installed_packages.get(
            candidate.package_id.casefold()
        )

        if package is None:
            continue

        icao = candidate.icao.strip().upper()

        if not re.fullmatch(r"[A-Z]{4}", icao):
            continue

        airport = catalog.get_by_code(icao)

        if airport is None:
            continue

        if airport.latitude is None or airport.longitude is None:
            continue

        if not (
            -90 <= airport.latitude <= 90
            and -180 <= airport.longitude <= 180
        ):
            continue

        airports[icao] = {
            "icao": icao,
            "name": airport.name,
            "latitude": airport.latitude,
            "longitude": airport.longitude,
            "package_id": package.package_id,
            "scenery_name": package.name,
        }

    airport_list = sorted(
        airports.values(),
        key=lambda airport: airport["icao"],
    )

    connections = [
        {
            "departure_icao": departure["icao"],
            "arrival_icao": arrival["icao"],
        }
        for departure, arrival in combinations(airport_list, 2)
    ]

    return {
        "source": "installed_addon_inventory",
        "airport_count": len(airport_list),
        "connection_count": len(connections),
        "airports": airport_list,
        "connections": connections,
        "warnings": inventory.warnings,
    }
