
from dataclasses import dataclass
from functools import lru_cache

import airportsdata


@dataclass(frozen=True)
class AirportData:
    icao_code: str
    iata_code: str | None
    name: str
    city: str
    country: str
    latitude: float
    longitude: float
    elevation_ft: int | None
    timezone: str | None


class AirportProvider:

    def __init__(self):
        self._icao_airports = airportsdata.load("ICAO")
        self._iata_airports = airportsdata.load("IATA")

    @staticmethod
    def _convert(data: dict) -> AirportData:
        return AirportData(
            icao_code=data["icao"],
            iata_code=data["iata"] or None,
            name=data["name"],
            city=data["city"],
            country=data["country"],
            latitude=data["lat"],
            longitude=data["lon"],
            elevation_ft=data["elevation"],
            timezone=data["tz"] or None,
        )

    def get_by_code(self, code: str) -> AirportData | None:
        code = code.strip().upper()

        data = (
            self._icao_airports.get(code)
            or self._iata_airports.get(code)
        )

        return self._convert(data) if data else None

    
    def search(
        self,
        query: str = "",
        *,
        country: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[int, list[AirportData]]:

        query = query.strip().casefold()
        country = country.strip().casefold() if country else None

        matches = []

        for data in self._icao_airports.values():
            if country:
                airport_country = str(
                    data.get("country") or ""
                ).casefold()

                if airport_country != country:
                    continue

            searchable = (
                data.get("icao", ""),
                data.get("iata", ""),
                data.get("name", ""),
                data.get("city", ""),
            )

            if query and not any(
                query in str(value).casefold()
                for value in searchable
            ):
                continue

            matches.append(self._convert(data))

        matches.sort(key=lambda airport: airport.icao_code)

        total = len(matches)

        return total, matches[offset:offset + limit]


    def list_airports(self) -> list[AirportData]:
        return [
            self._convert(data)
            for data in self._icao_airports.values()
        ]


@lru_cache(maxsize=1)
def get_airport_provider() -> AirportProvider:
    return AirportProvider()
