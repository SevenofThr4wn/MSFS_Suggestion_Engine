from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.schemas.addon import AddonInventoryResponse
from app.services.addon_inventory_service import (
    AddonInventoryService,
)


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
