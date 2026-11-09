from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.repositories.airport_preferences_repository import (
    AirportPreferencesRepository,
)
from app.providers.airport_catalog import AirportCatalog
from app.providers.airport_provider import get_airport_provider
from app.providers.runway_provider import get_runway_provider
from app.providers.airport_metadata_provider import get_airport_metadata_provider

def get_airport_catalog(
    db: Annotated[Session, Depends(get_db)],
) -> AirportCatalog:

    return AirportCatalog(
    airport_provider=get_airport_provider(),
    runway_provider=get_runway_provider(),
    preferences=AirportPreferencesRepository(db),
    metadata_provider=get_airport_metadata_provider(),
    )
