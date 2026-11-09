import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
RUNWAY_FILE = BASE_DIR / "data" / "runways.csv"

FT_TO_M = 0.3048


@dataclass(frozen=True)
class RunwayData:
    id: int
    airport_icao: str
    designation: str
    length_m: float | None
    width_m: float | None
    surface: str | None
    lighted: bool
    closed: bool


class RunwayProvider:
    def __init__(self, filename: Path = RUNWAY_FILE):
        if not filename.is_file():
            raise FileNotFoundError(
                f"Missing runway data: {filename}"
            )

        self._runways: dict[str, list[RunwayData]] = {}

        with filename.open(
            encoding="utf-8-sig",
            newline="",
        ) as file:
            for row in csv.DictReader(file):
                code = row["airport_ident"].strip().upper()

                runway = RunwayData(
                    id=int(row["id"]),
                    airport_icao=code,
                    designation=(
                        f"{row.get('le_ident') or '?'}"
                        f"/{row.get('he_ident') or '?'}"
                    ),
                    length_m=self._meters(
                        row.get("length_ft")
                    ),
                    width_m=self._meters(
                        row.get("width_ft")
                    ),
                    surface=row.get("surface") or None,
                    lighted=row.get("lighted") == "1",
                    closed=row.get("closed") == "1",
                )

                self._runways.setdefault(code, []).append(
                    runway
                )

    @staticmethod
    def _meters(value: str | None) -> float | None:
        if not value:
            return None

        try:
            result = float(value) * FT_TO_M
            return round(result, 2) if result > 0 else None
        except ValueError:
            return None

    def get_by_airport(
        self,
        code: str,
        *,
        include_closed: bool = False,
    ) -> list[RunwayData]:

        runways = self._runways.get(
            code.strip().upper(),
            [],
        )

        if include_closed:
            return list(runways)

        return [
            r for r in runways
            if not r.closed
        ]


@lru_cache(maxsize=1)
def get_runway_provider() -> RunwayProvider:
    return RunwayProvider()
