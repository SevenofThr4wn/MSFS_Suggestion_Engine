import csv

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]

AIRPORT_METADATA_FILE = (
    BASE_DIR / "data" / "airports.csv"
)


@dataclass(frozen=True)
class AirportMetadata:
    ident: str
    icao_code: str | None
    airport_type: str
    scheduled_service: bool
    closed: bool


class AirportMetadataProvider:

    def __init__(
        self,
        filename: Path = AIRPORT_METADATA_FILE,
    ):
        self._airports: dict[str, AirportMetadata] = {}
        self._by_ident: dict[str, AirportMetadata] = {}

        with filename.open(
            encoding="utf-8-sig",
            newline="",
        ) as file:
            reader = csv.DictReader(file)

            for row in reader:
                ident = (
                    row.get("ident") or ""
                ).strip().upper()

                icao = (
                    row.get("icao_code") or ""
                ).strip().upper() or None

                airport_type = (
                    row.get("type") or "unknown"
                ).strip().lower()

                metadata = AirportMetadata(
                    ident=ident,
                    icao_code=icao,
                    airport_type=airport_type,
                    scheduled_service=(
                        (row.get("scheduled_service") or "")
                        .strip().lower() == "yes"
                    ),
                    closed=(airport_type == "closed"),
                )

                if ident:
                    self._by_ident[ident] = metadata

                # Prefer an explicit ICAO code.
                if icao:
                    self._airports[icao] = metadata

                # Fall back to OurAirports ident.
                if ident and ident not in self._airports:
                    self._airports[ident] = metadata

    def get_by_code(
        self,
        code: str,
    ) -> AirportMetadata | None:

        normalized = code.strip().upper()

        return self._airports.get(normalized)


@lru_cache(maxsize=1)
def get_airport_metadata_provider():
    return AirportMetadataProvider()
