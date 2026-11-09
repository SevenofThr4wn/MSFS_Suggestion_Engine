from dataclasses import dataclass

from app.providers.airport_provider import (
    AirportData,
    AirportProvider,
)
from app.providers.runway_provider import (
    RunwayData,
    RunwayProvider,
)
from app.db.repositories.airport_preferences_repository import (
    AirportPreferencesRepository,
)

from app.providers.airport_metadata_provider import (
    AirportMetadataProvider,
)


@dataclass(frozen=True)
class AirportRecord:
    icao_code: str
    iata_code: str | None
    name: str
    city: str | None
    country: str | None

    latitude: float
    longitude: float
    elevation_ft: int | None
    timezone: str | None

    airport_type: str | None
    scheduled_service: bool | None
    is_closed: bool | None

    has_addon_scenery: bool
    scenery_developer: str | None
    is_favourite: bool

    

    runways: tuple[RunwayData, ...]


class AirportCatalog:
    def __init__(
        self,
        airport_provider: AirportProvider,
        runway_provider: RunwayProvider,
        preferences: AirportPreferencesRepository,
        metadata_provider: AirportMetadataProvider
    ):
        self.airports = airport_provider
        self.runways = runway_provider
        self.preferences = preferences
        self.metadata = metadata_provider

    def build(self, airport: AirportData) -> AirportRecord:
        prefs = self.preferences.get(airport.icao_code)

        metadata = self.metadata.get_by_code(
            airport.icao_code
        )

        runway_code = (
            metadata.ident
            if metadata is not None
            else airport.icao_code
        )

        return AirportRecord(
            **vars(airport),

            airport_type=(
                metadata.airport_type if metadata else None
            ),

            scheduled_service=(
                metadata.scheduled_service if metadata else None
            ),

            is_closed=(
                metadata.closed if metadata else None
            ),

            has_addon_scenery=(
                prefs.has_addon_scenery if prefs else False
            ),

            scenery_developer=(
                prefs.scenery_developer if prefs else None
            ),

            is_favourite=(
                prefs.is_favourite if prefs else False
            ),

            runways=tuple(
                self.runways.get_by_airport(runway_code)
            ),
        )

    def get_by_code(
        self,
        code: str,
    ) -> AirportRecord | None:

        airport = self.airports.get_by_code(code)

        return self.build(airport) if airport else None

    def search(
        self,
        query: str = "",
        *,
        country: str | None = None,
        addon_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[int, list[AirportRecord]]:

        # Apply local preference filtering before pagination.
        total, airports = self.airports.search(
            query,
            country=country,
            limit=len(self.airports.list_airports()),
        )

        if addon_only:
            addon_codes = self.preferences.list_addon_codes()
            airports = [
                a for a in airports
                if a.icao_code in addon_codes
            ]

        total = len(airports)

        return total, [
            self.build(a)
            for a in airports[offset:offset + limit]
        ]
