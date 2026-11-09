from __future__ import annotations

import argparse
import csv
import math
from collections import Counter, defaultdict
from pathlib import Path


SOURCE = "openflights_historical_2014"

OUTPUT_COLUMNS = [
    "airline_icao",
    "departure_icao",
    "arrival_icao",
    "distance_nm",
    "aircraft_icao",
    "source",
    "source_reference",
]


def clean(value: str | None) -> str | None:
    """Normalize missing OpenFlights field values."""
    if value is None:
        return None

    value = value.strip()

    if not value or value == "\\N":
        return None

    return value


def read_rows(path: Path, expected_columns: int):
    """Yield validated CSV rows and their source line numbers."""
    if not path.is_file():
        raise FileNotFoundError(f"Missing dataset: {path}")

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        for line_number, row in enumerate(
            csv.reader(file),
            start=1,
        ):
            if not row:
                continue

            if len(row) != expected_columns:
                raise ValueError(
                    f"{path.name}:{line_number}: "
                    f"expected {expected_columns} fields, "
                    f"received {len(row)}"
                )

            yield line_number, row


def is_airport_icao(code: str | None) -> bool:
    """Validate an airport ICAO identifier."""
    return (
        code is not None
        and len(code) == 4
        and code.isalpha()
    )


def is_aircraft_icao(code: str | None) -> bool:
    """Validate an ICAO aircraft type designator."""
    return (
        code is not None
        and 2 <= len(code) <= 4
        and code.isascii()
        and code.isalnum()
    )


def distance_nm(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """Calculate great-circle distance in nautical miles."""
    latitude1 = math.radians(lat1)
    longitude1 = math.radians(lon1)
    latitude2 = math.radians(lat2)
    longitude2 = math.radians(lon2)

    a = (
        math.sin((latitude2 - latitude1) / 2) ** 2
        + math.cos(latitude1)
        * math.cos(latitude2)
        * math.sin((longitude2 - longitude1) / 2) ** 2
    )

    a = min(1.0, max(0.0, a))

    return 3440.065 * 2 * math.asin(math.sqrt(a))


def load_airports(path: Path) -> dict[str, tuple]:
    """Map OpenFlights airport IDs to ICAO and coordinates."""
    result = {}

    for _, row in read_rows(path, 14):
        airport_id = clean(row[0])
        icao = clean(row[5])

        if not airport_id or not is_airport_icao(icao):
            continue

        try:
            latitude = float(row[6])
            longitude = float(row[7])
        except ValueError:
            continue

        if not (
            -90 <= latitude <= 90
            and -180 <= longitude <= 180
        ):
            continue

        result[airport_id] = (
            icao.upper(),
            latitude,
            longitude,
        )

    return result


def load_airlines(path: Path) -> dict[str, str]:
    """Map OpenFlights airline IDs to ICAO airline codes."""
    result = {}

    for _, row in read_rows(path, 8):
        airline_id = clean(row[0])
        icao = clean(row[4])

        if (
            airline_id
            and icao
            and len(icao) == 3
            and icao.isalpha()
        ):
            result[airline_id] = icao.upper()

    return result


def load_aircraft(path: Path) -> dict[str, str]:
    """
    Resolve IATA equipment codes to unambiguous ICAO types.

    Equipment codes mapping to several ICAO aircraft types
    are excluded to prevent incorrect training labels.
    """
    candidates = defaultdict(set)

    for _, row in read_rows(path, 3):
        iata = clean(row[1])
        icao = clean(row[2])

        if not iata or not is_aircraft_icao(icao):
            continue

        candidates[iata.upper()].add(icao.upper())

    return {
        iata: next(iter(codes))
        for iata, codes in candidates.items()
        if len(codes) == 1
    }


def build_dataset(
    source_directory: Path,
    output_path: Path,
) -> None:
    """Build a historical aircraft-assignment training dataset."""
    airports = load_airports(
        source_directory / "airports.dat"
    )
    airlines = load_airlines(
        source_directory / "airlines.dat"
    )
    aircraft = load_aircraft(
        source_directory / "planes.dat"
    )

    counters = Counter()
    records = {}
    conflicting_keys = set()

    for line_number, row in read_rows(
        source_directory / "routes.dat",
        9,
    ):
        counters["input_routes"] += 1

        (
            _airline_code,
            airline_id,
            _departure_code,
            departure_id,
            _arrival_code,
            arrival_id,
            codeshare,
            stops,
            equipment,
        ) = row

        # Exclude marketing codeshares.
        if clean(codeshare) == "Y":
            counters["codeshare_skipped"] += 1
            continue

        # Only nonstop routes.
        if clean(stops) != "0":
            counters["connecting_routes_skipped"] += 1
            continue

        airline = airlines.get(
            clean(airline_id) or ""
        )
        departure = airports.get(
            clean(departure_id) or ""
        )
        arrival = airports.get(
            clean(arrival_id) or ""
        )

        if not airline or not departure or not arrival:
            counters["unresolved_identifiers"] += 1
            continue

        dep_icao, dep_lat, dep_lon = departure
        arr_icao, arr_lat, arr_lon = arrival

        if dep_icao == arr_icao:
            counters["same_airport_skipped"] += 1
            continue

        route_distance = distance_nm(
            dep_lat,
            dep_lon,
            arr_lat,
            arr_lon,
        )

        if not 0 < route_distance <= 20000:
            counters["invalid_distance"] += 1
            continue

        equipment_codes = (
            (clean(equipment) or "").upper().split()
        )

        if not equipment_codes:
            counters["no_equipment"] += 1
            continue

        for equipment_code in set(equipment_codes):
            aircraft_icao = aircraft.get(equipment_code)

            if not aircraft_icao:
                counters["unmapped_equipment"] += 1
                continue

            key = (
                airline,
                dep_icao,
                arr_icao,
                aircraft_icao,
            )

            # Keep one observation per historical combination.
            # Different rows for a combination can contain
            # inconsistent reference details: don't invent
            # independent training observations.
            record = {
                "airline_icao": airline,
                "departure_icao": dep_icao,
                "arrival_icao": arr_icao,
                "distance_nm": round(route_distance, 2),
                "aircraft_icao": aircraft_icao,
                "source": SOURCE,
                "source_reference": (
                    f"openflights:routes.dat:{line_number}"
                ),
            }

            if key in records:
                counters["duplicates_skipped"] += 1
                continue

            records[key] = record
            counters["accepted_combinations"] += 1

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=OUTPUT_COLUMNS,
        )
        writer.writeheader()

        for key in sorted(records):
            writer.writerow(records[key])

    print("\nFlightEngine ML Dataset")
    print("=" * 48)
    print(f"Airports mapped: {len(airports):,}")
    print(f"Airlines mapped: {len(airlines):,}")
    print(f"Aircraft types mapped: {len(aircraft):,}")

    for key, value in sorted(counters.items()):
        print(f"{key}: {value:,}")

    print(f"\nOutput: {output_path.resolve()}")
    print(f"Training rows: {len(records):,}")
    print("\nEvidence: Historical OpenFlights route data.")
    print("These records do not verify current airline service.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build FlightEngine's historical ML dataset."
    )

    parser.add_argument(
        "--source",
        type=Path,
        default=Path("data/openflights"),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "data/ml/aircraft_assignments.csv"
        ),
    )

    args = parser.parse_args()

    build_dataset(
        source_directory=args.source,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
