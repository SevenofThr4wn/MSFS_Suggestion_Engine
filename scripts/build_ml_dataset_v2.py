from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd


BASE = Path("data")
ML_DIR = BASE / "ml"
RECENT_DIR = BASE / "bts"
REFERENCE_DIR = BASE / "reference"

OURAIRPORTS_URL = (
    "https://raw.githubusercontent.com/"
    "davidmegginson/ourairports-data/main/airports.csv"
)

OUTPUT_COLUMNS = [
    "airline_icao",
    "departure_icao",
    "arrival_icao",
    "distance_nm",
    "aircraft_icao",
    "source",
    "source_reference",
]

AUDIT_COLUMNS = [
    "type",
    "identifier",
    "count",
]


def normalize(value: object) -> str:
    if pd.isna(value):
        return ""

    result = str(value).strip().upper()

    if result in {"NAN", "NONE", "NULL", "\\N"}:
        return ""

    return result


def is_icao(value: str) -> bool:
    return bool(
        re.fullmatch(r"[A-Z0-9]{2,4}", value)
    )


def download_file(
    url: str,
    destination: Path,
    refresh: bool = False,
) -> None:
    if (
        destination.is_file()
        and destination.stat().st_size > 0
        and not refresh
    ):
        print(f"Using cached: {destination}")
        return

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    request = Request(
        url,
        headers={
            "User-Agent": "FlightEngine/2.0",
        },
    )

    temporary = destination.with_suffix(
        destination.suffix + ".download"
    )

    try:
        with urlopen(request, timeout=60) as response:
            with temporary.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)

        if temporary.stat().st_size == 0:
            raise ValueError("Downloaded file is empty.")

        temporary.replace(destination)

    finally:
        temporary.unlink(missing_ok=True)


def load_airports(path: Path) -> dict[str, str]:
    data = pd.read_csv(
        path,
        dtype=str,
        low_memory=False,
    )

    required = {
        "ident",
        "iata_code",
        "gps_code",
    }

    missing = required - set(data.columns)

    if missing:
        raise ValueError(
            f"Airport dataset missing: {sorted(missing)}"
        )

    # Reject ambiguous IATA-to-ICAO mappings rather
    # than arbitrarily selecting one airport.
    candidates: dict[str, set[str]] = {}

    for row in data.itertuples(index=False):
        values = row._asdict()

        iata = normalize(values["iata_code"])
        gps = normalize(values["gps_code"])
        ident = normalize(values["ident"])

        icao = gps or ident

        if (
            len(iata) != 3
            or not re.fullmatch(r"[A-Z]{4}", icao)
        ):
            continue

        candidates.setdefault(
            iata,
            set(),
        ).add(icao)

    return {
        iata: next(iter(codes))
        for iata, codes in candidates.items()
        if len(codes) == 1
    }


def load_mapping(
    path: Path,
    source_column: str,
    target_column: str,
) -> dict[str, str]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Required mapping missing: {path}"
        )

    data = pd.read_csv(
        path,
        dtype=str,
    )

    required = {
        source_column,
        target_column,
    }

    if not required.issubset(data.columns):
        raise ValueError(
            f"{path} needs columns: {sorted(required)}"
        )

    candidates: dict[str, set[str]] = {}

    for row in data.to_dict("records"):
        source = normalize(row[source_column])
        target = normalize(row[target_column])

        if source and target:
            candidates.setdefault(
                source,
                set(),
            ).add(target)

    return {
        source: next(iter(targets))
        for source, targets in candidates.items()
        if len(targets) == 1
    }


def find_column(
    dataframe: pd.DataFrame,
    *names: str,
) -> str:
    lookup = {
        column.upper().strip(): column
        for column in dataframe.columns
    }

    for name in names:
        column = lookup.get(name.upper())

        if column:
            return column

    raise ValueError(
        f"Missing required column. Expected one of: {names}"
    )


def convert_t100(
    path: Path,
    airports: dict[str, str],
    airlines: dict[str, str],
    aircraft: dict[str, str],
    audit: Counter,
) -> list[dict]:
    records = []

    print(f"Reading BTS: {path.name}")

    data = pd.read_csv(
        path,
        dtype=str,
        low_memory=False,
    )

    carrier_col = find_column(
        data,
        "UNIQUE_CARRIER",
        "CARRIER",
    )

    origin_col = find_column(data, "ORIGIN")
    destination_col = find_column(data, "DEST")
    equipment_col = find_column(data, "AIRCRAFT_TYPE")
    performed_col = find_column(
        data,
        "DEPARTURES_PERFORMED",
        "DEP_PERFORMED",
    )

    year_col = find_column(data, "YEAR")
    month_col = find_column(data, "MONTH")

    for index, row in enumerate(
        data.to_dict("records"),
        start=2,
    ):
        audit[("input_rows", "")] += 1

        carrier = normalize(row[carrier_col])
        origin = normalize(row[origin_col])
        destination = normalize(row[destination_col])
        equipment = normalize(row[equipment_col])

        airline_icao = airlines.get(carrier)
        departure_icao = airports.get(origin)
        arrival_icao = airports.get(destination)
        aircraft_icao = aircraft.get(equipment)

        if not airline_icao:
            audit[("unmapped_carrier", carrier)] += 1
            continue

        if not departure_icao or not arrival_icao:
            if not departure_icao:
                audit[("unmapped_airport", origin)] += 1

            if not arrival_icao:
                audit[("unmapped_airport", destination)] += 1

            continue

        if not aircraft_icao:
            audit[("unmapped_aircraft", equipment)] += 1
            continue

        if not is_icao(aircraft_icao):
            audit[("invalid_aircraft_code", equipment)] += 1
            continue

        if departure_icao == arrival_icao:
            continue

        try:
            departures = float(row[performed_col])
            year = int(float(row[year_col]))
            month = int(float(row[month_col]))
        except (TypeError, ValueError):
            continue

        if (
            departures <= 0
            or not 1 <= month <= 12
            or not 2020 <= year <= 2100
        ):
            continue

        records.append({
            "airline_icao": airline_icao,
            "departure_icao": departure_icao,
            "arrival_icao": arrival_icao,
            "aircraft_icao": aircraft_icao,
            "year": year,
            "month": month,
            "departures_performed": departures,
            "source": "bts_t100",
            "source_reference": (
                f"{path.name}:row:{index}"
            ),
        })

        audit[("accepted_rows", "")] += 1

    return records


def load_historical(path: Path) -> pd.DataFrame:
    if not path.is_file() or path.stat().st_size == 0:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    data = pd.read_csv(path)

    missing = set(OUTPUT_COLUMNS) - set(data.columns)

    if missing:
        raise ValueError(
            f"Historical dataset missing: {sorted(missing)}"
        )

    return data[OUTPUT_COLUMNS].copy()


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--bts",
        type=Path,
        default=RECENT_DIR,
    )

    parser.add_argument(
        "--historical",
        type=Path,
        default=ML_DIR / "aircraft_assignments.csv",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=ML_DIR / "aircraft_assignments_v2.csv",
    )

    parser.add_argument(
        "--refresh-airports",
        action="store_true",
    )

    args = parser.parse_args()

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    airport_path = REFERENCE_DIR / "airports.csv"

    download_file(
        OURAIRPORTS_URL,
        airport_path,
        refresh=args.refresh_airports,
    )

    airports = load_airports(airport_path)

    airlines = load_mapping(
        REFERENCE_DIR / "bts_airlines.csv",
        "bts_code",
        "airline_icao",
    )

    aircraft = load_mapping(
        REFERENCE_DIR / "bts_aircraft.csv",
        "bts_code",
        "aircraft_icao",
    )

    audit = Counter()
    recent = []

    files = sorted(args.bts.glob("*.csv"))

    if not files:
        raise FileNotFoundError(
            "No BTS CSV files found. Download T-100 "
            f"Segment files into {args.bts}"
        )

    for file in files:
        recent.extend(
            convert_t100(
                file,
                airports,
                airlines,
                aircraft,
                audit,
            )
        )

    recent_data = pd.DataFrame(recent)

    if recent_data.empty:
        raise ValueError(
            "No BTS rows could be mapped. Check the "
            "unmapped carrier and aircraft identifiers."
        )

    # Preserve a detailed monthly dataset separately.
    detailed_path = (
        args.output.parent / "bts_assignments_detailed.csv"
    )

    recent_data.to_csv(
        detailed_path,
        index=False,
    )

    # Group observations by airline-route-aircraft.
    # The legacy model expects one row per combination,
    # but we retain the flight counts separately.
    keys = [
        "airline_icao",
        "departure_icao",
        "arrival_icao",
        "aircraft_icao",
    ]

    grouped = (
        recent_data.groupby(keys, as_index=False)
        .agg(
            departures_performed=(
                "departures_performed",
                "sum",
            ),
            last_year=("year", "max"),
        )
    )

    # Compute distance using current airport metadata
    # via the project's existing haversine function.
    from scripts.build_ml_dataset import distance_nm

    airport_data = pd.read_csv(
        airport_path,
        dtype=str,
    )

    coordinates = {}

    for row in airport_data.to_dict("records"):
        iata = normalize(row.get("iata_code"))

        if iata not in airports:
            continue

        try:
            lat = float(row["latitude_deg"])
            lon = float(row["longitude_deg"])
        except (TypeError, ValueError):
            continue

        icao = airports[iata]

        coordinates.setdefault(icao, (lat, lon))

    def calculate_distance(row) -> float | None:
        departure = coordinates.get(row["departure_icao"])
        arrival = coordinates.get(row["arrival_icao"])

        if departure is None or arrival is None:
            return None

        return round(
            distance_nm(
                departure[0],
                departure[1],
                arrival[0],
                arrival[1],
            ),
            2,
        )

    grouped["distance_nm"] = grouped.apply(
        calculate_distance,
        axis=1,
    )

    grouped = grouped.dropna(
        subset=["distance_nm"],
    )

    grouped = grouped[
        grouped["distance_nm"] > 0
    ].copy()

    grouped["source"] = "bts_t100"

    grouped["source_reference"] = grouped.apply(
        lambda row: (
            f"bts_t100:{row['airline_icao']}:"
            f"{row['departure_icao']}:"
            f"{row['arrival_icao']}:"
            f"{row['aircraft_icao']}"
        ),
        axis=1,
    )

    recent_training = grouped[
        OUTPUT_COLUMNS
    ].copy()

    historical = load_historical(args.historical)

    combined = pd.concat(
        [recent_training, historical],
        ignore_index=True,
    )

    # BTS wins when a historical assignment duplicates
    # a more recent, mapped airline-route-aircraft record.
    combined = combined.drop_duplicates(
        subset=keys,
        keep="first",
    )

    combined.to_csv(
        args.output,
        index=False,
    )

    audit_path = (
        args.output.parent / "bts_mapping_audit.csv"
    )

    audit_rows = [
        {
            "type": kind,
            "identifier": identifier,
            "count": count,
        }
        for (kind, identifier), count in audit.items()
    ]

    pd.DataFrame(
        audit_rows,
        columns=AUDIT_COLUMNS,
    ).sort_values(
        ["type", "count"],
        ascending=[True, False],
    ).to_csv(
        audit_path,
        index=False,
    )

    print("\nFlightEngine ML Dataset V2")
    print("=" * 48)
    print(f"Recent observations: {len(recent):,}")
    print(f"Recent combinations: {len(recent_training):,}")
    print(f"Historical combinations: {len(historical):,}")
    print(f"Combined combinations: {len(combined):,}")
    print(f"Output: {args.output}")
    print(f"Detailed BTS: {detailed_path}")
    print(f"Mapping audit: {audit_path}")
    print("\nCurrent schedules have NOT been verified.")


if __name__ == "__main__":
    main()
