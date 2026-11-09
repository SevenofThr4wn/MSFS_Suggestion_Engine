from __future__ import annotations

import argparse
import csv
import re
from rapidfuzz import fuzz, process
from collections import Counter, defaultdict
from pathlib import Path


DATA_DIR = Path("data")
REFERENCE_DIR = DATA_DIR / "reference"
OPENFLIGHTS_DIR = DATA_DIR / "openflights"
BTS_DIR = DATA_DIR / "bts"

CARRIERS_FILE = REFERENCE_DIR / "L_UNIQUE_CARRIERS.csv"
AIRCRAFT_FILE = REFERENCE_DIR / "T_AIRCRAFT_TYPES.csv"
SEGMENTS_FILE = BTS_DIR / "T_T100_SEGMENT_ALL_CARRIER.csv"

AIRLINES_OUTPUT = REFERENCE_DIR / "bts_airlines.csv"
AIRCRAFT_OUTPUT = REFERENCE_DIR / "bts_aircraft.csv"
AUDIT_DIR = REFERENCE_DIR / "mapping_audit"


# Conservative aircraft mappings.
# Each pattern identifies one specific ICAO aircraft type.
# Ambiguous models deliberately remain unresolved.

AIRCRAFT_PATTERNS = (
    # Airbus A220
    (r"\b(?:A220|BD 500)\s*100\b", "BCS1"),
    (r"\b(?:A220|BD 500)\s*300\b", "BCS3"),

    # Airbus A320 family: specific models before generic
    (r"\bA319\s*NEO\b", "A19N"),
    (r"\bA320\s*NEO\b", "A20N"),
    (r"\bA321\s*NEO\b", "A21N"),
    (r"\bA319(?:\s*100|\s*200)?\b", "A319"),
    (r"\bA320(?:\s*100|\s*200)?\b", "A320"),
    (r"\bA321(?:\s*100|\s*200)?\b", "A321"),

    # Airbus widebodies
    (r"\bA300\s*600\b", "A306"),
    (r"\bA310\s*300\b", "A313"),
    (r"\bA330\s*200\b", "A332"),
    (r"\bA330\s*300\b", "A333"),
    (r"\bA340\s*200\b", "A342"),
    (r"\bA340\s*300\b", "A343"),
    (r"\bA340\s*500\b", "A345"),
    (r"\bA340\s*600\b", "A346"),
    (r"\bA350\s*900\b", "A359"),
    (r"\bA350\s*1000\b", "A35K"),
    (r"\bA380\s*800\b", "A388"),

    # Boeing 717 / 737
    (r"\b717\s*200\b", "B712"),
    (r"\b737\s*MAX\s*7\b", "B37M"),
    (r"\b737\s*MAX\s*8\b", "B38M"),
    (r"\b737\s*MAX\s*9\b", "B39M"),
    (r"\b737\s*MAX\s*10\b", "B3XM"),
    (r"\b737\s*300\b", "B733"),
    (r"\b737\s*400\b", "B734"),
    (r"\b737\s*500\b", "B735"),
    (r"\b737\s*600\b", "B736"),
    (r"\b737\s*700\b", "B737"),
    (r"\b737\s*800\b", "B738"),
    (r"\b737\s*900\b", "B739"),

    # Boeing widebodies
    (r"\b747\s*400\b", "B744"),
    (r"\b747\s*8(?:F|I)?\b", "B748"),
    (r"\b757\s*200\b", "B752"),
    (r"\b757\s*300\b", "B753"),
    (r"\b767\s*200\b", "B762"),
    (r"\b767\s*300\b", "B763"),
    (r"\b767\s*400\b", "B764"),
    (r"\b777\s*200\s*LR\b", "B77L"),
    (r"\b777\s*200\s*ER\b", "B772"),
    (r"\b777\s*300\s*ER\b", "B77W"),
    (r"\b777\s*200\b", "B772"),
    (r"\b777\s*300\b", "B773"),
    (r"\b787\s*8\b", "B788"),
    (r"\b787\s*9\b", "B789"),
    (r"\b787\s*10\b", "B78X"),

    # Embraer regional jets
    (r"\b(?:ERJ|EMB|E)\s*170\b", "E170"),
    (r"\b(?:ERJ|EMB|E)\s*175\b", "E75L"),
    (r"\b(?:ERJ|EMB|E)\s*190\b", "E190"),
    (r"\b(?:ERJ|EMB|E)\s*195\b", "E195"),

    # Bombardier / Canadair CRJ
    (r"\bCRJ\s*200\b", "CRJ2"),
    (r"\bCRJ\s*700\b", "CRJ7"),
    (r"\bCRJ\s*900\b", "CRJ9"),
    (r"\bCRJ\s*1000\b", "CRJX"),

    # De Havilland Dash 8
    (r"\b(?:DHC\s*8|DASH\s*8)\s*100\b", "DH8A"),
    (r"\b(?:DHC\s*8|DASH\s*8)\s*200\b", "DH8B"),
    (r"\b(?:DHC\s*8|DASH\s*8)\s*300\b", "DH8C"),
    (r"\b(?:DHC\s*8|DASH\s*8)\s*400\b", "DH8D"),

    # ATR
    (r"\bATR\s*42\b", "AT43"),
    (r"\bATR\s*72\b", "AT72"),
)



def normalize_name(value: str | None) -> str:
    if not value:
        return ""

    value = value.upper().strip()
    value = value.replace("&", " AND ")
    value = re.sub(r"[^A-Z0-9]+", " ", value)

    return " ".join(value.split())


def clean(value: str | None) -> str:
    return (value or "").strip().upper()


def read_csv(path: Path):
    if not path.is_file():
        raise FileNotFoundError(
            f"Required file not found: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        yield from csv.DictReader(file)


def write_csv(
    path: Path,
    fieldnames: list[str],
    rows: list[dict],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)


def load_openflights_airlines() -> dict[str, set[str]]:
    path = OPENFLIGHTS_DIR / "airlines.dat"

    names: dict[str, set[str]] = defaultdict(set)

    if not path.is_file():
        raise FileNotFoundError(path)

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        for row in csv.reader(file):
            if len(row) < 5:
                continue

            name = normalize_name(row[1])
            alias = normalize_name(row[2])
            icao = clean(row[4])

            if not re.fullmatch(r"[A-Z]{3}", icao):
                continue

            for candidate in (name, alias):
                if candidate and candidate != "N":
                    names[candidate].add(icao)

    return names


def build_airline_mappings():
    lookup = load_openflights_airlines()

    mapped = []
    unresolved = []

    known_names = list(lookup)

    for row in read_csv(CARRIERS_FILE):
        bts_code = clean(row.get("Code"))
        description = row.get("Description", "")

        if not bts_code:
            continue

        normalized = normalize_name(description)
        candidates = lookup.get(normalized, set())

        if len(candidates) == 1:
            mapped.append({
                "bts_code": bts_code,
                "airline_icao": next(iter(candidates)),
            })
        
    else:
        suggestions = process.extract(
            normalized,
            known_names,
            scorer=fuzz.WRatio,
            limit=3,
            score_cutoff=70,
        )

        suggested_codes = []

        for name, score, _ in suggestions:
            for icao in sorted(lookup[name]):
                suggested_codes.append(
                    f"{icao}:{score:.1f}"
                )

        unresolved.append({
            "bts_code": bts_code,
            "description": description,
            "reason": (
                "ambiguous"
                if candidates
                else "no_exact_name_match"
            ),
            "candidates": "|".join(
                suggested_codes
            ),
        })


    return mapped, unresolved



def identify_aircraft(
    description: str,
    manufacturer: str,
) -> str | None:
    text = normalize_name(description)
    maker = normalize_name(manufacturer)

    # Normalise variant-specific descriptions.
    # Require explicit family evidence to prevent
    # unrelated numeric identifiers matching.
    families = {
        "AIRBUS": ("A220", "A300", "A310", "A319",
                   "A320", "A321", "A330", "A340",
                   "A350", "A380"),
        "BOEING": ("717", "737", "747", "757",
                   "767", "777", "787"),
        "EMBRAER": ("170", "175", "190", "195"),
        "BOMBARDIER": ("CRJ", "DHC", "DASH", "BD"),
    }

    known_family = any(
        family in text
        for options in families.values()
        for family in options
    )

    if not known_family:
        return None

    # More specific patterns appear before generic ones.
    for pattern, aircraft_icao in AIRCRAFT_PATTERNS:
        if re.search(pattern, text):
            return aircraft_icao

    return None


def build_aircraft_mappings():
    mapped = []
    unresolved = []

    for row in read_csv(AIRCRAFT_FILE):
        bts_code = clean(row.get("AC_TYPEID"))

        if not bts_code:
            continue

        manufacturer = row.get("MANUFACTURER", "")
        long_name = row.get("LONG_NAME", "")
        short_name = row.get("SHORT_NAME", "")
        description = row.get("SSD_NAME", "")

        aircraft_icao = (
            identify_aircraft(
                description,
                manufacturer,
            )
            or identify_aircraft(
                long_name,
                manufacturer,
            )
        )

        if aircraft_icao:
            mapped.append({
                "bts_code": bts_code,
                "aircraft_icao": aircraft_icao,
            })
        else:
            unresolved.append({
                "bts_code": bts_code,
                "manufacturer": manufacturer,
                "description": description,
                "long_name": long_name,
                "short_name": short_name,
            })

    return mapped, unresolved


def audit_t100_coverage(
    airline_mappings: list[dict],
    aircraft_mappings: list[dict],
) -> dict:
    airline_codes = {
        row["bts_code"]
        for row in airline_mappings
    }

    aircraft_codes = {
        row["bts_code"]
        for row in aircraft_mappings
    }

    statistics = Counter()
    missing_carriers = Counter()
    missing_aircraft = Counter()

    for row in read_csv(SEGMENTS_FILE):
        carrier = clean(row.get("UNIQUE_CARRIER"))
        aircraft = clean(row.get("AIRCRAFT_TYPE"))

        try:
            departures = float(
                row.get("DEPARTURES_PERFORMED") or 0
            )
        except ValueError:
            departures = 0

        if departures <= 0:
            continue

        if clean(row.get("ORIGIN")) == clean(row.get("DEST")):
            continue

        statistics["total_rows"] += 1
        statistics["total_departures"] += departures

        carrier_ok = carrier in airline_codes
        aircraft_ok = aircraft in aircraft_codes

        if not carrier_ok:
            missing_carriers[carrier] += departures

        if not aircraft_ok:
            missing_aircraft[aircraft] += departures

        if carrier_ok and aircraft_ok:
            statistics["mapped_rows"] += 1
            statistics["mapped_departures"] += departures

    write_csv(
        AUDIT_DIR / "missing_carriers.csv",
        ["bts_code", "departures"],
        [
            {
                "bts_code": code,
                "departures": count,
            }
            for code, count in missing_carriers.most_common()
        ],
    )

    write_csv(
        AUDIT_DIR / "missing_aircraft.csv",
        ["bts_code", "departures"],
        [
            {
                "bts_code": code,
                "departures": count,
            }
            for code, count in missing_aircraft.most_common()
        ],
    )

    return dict(statistics)


def apply_overrides(
    generated: list[dict],
    path: Path,
    target_field: str,
) -> list[dict]:
    mappings = {
        row["bts_code"]: row[target_field]
        for row in generated
    }

    if not path.is_file():
        return [
            {
                "bts_code": code,
                target_field: value,
            }
            for code, value in sorted(mappings.items())
        ]

    for row in read_csv(path):
        code = clean(row.get("bts_code"))
        value = clean(row.get(target_field))

        if not code or not value:
            continue

        if not re.fullmatch(r"[A-Z0-9]{2,4}", value):
            raise ValueError(
                f"Invalid override: {code} -> {value}"
            )

        mappings[code] = value

    return [
        {
            "bts_code": code,
            target_field: value,
        }
        for code, value in sorted(mappings.items())
    ]



def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build FlightEngine BTS ICAO mappings."
    )

    parser.parse_args()

    AUDIT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("Building airline mappings...")

    airlines, missing_airlines = (
        build_airline_mappings()
    )

    print("Building aircraft mappings...")

    aircraft, missing_aircraft = (
        build_aircraft_mappings()
    )

    airlines = apply_overrides(
        airlines,
        REFERENCE_DIR / "bts_airline_overrides.csv",
        "airline_icao",
    )

    aircraft = apply_overrides(
        aircraft,
        REFERENCE_DIR / "bts_aircraft_overrides.csv",
        "aircraft_icao",
    )

    write_csv(
        AIRLINES_OUTPUT,
        ["bts_code", "airline_icao"],
        airlines,
    )

    write_csv(
        AIRCRAFT_OUTPUT,
        ["bts_code", "aircraft_icao"],
        aircraft,
    )

    write_csv(
        AUDIT_DIR / "unresolved_airlines.csv",
        [
            "bts_code",
            "description",
            "reason",
            "candidates",
        ],
        missing_airlines,
    )

    write_csv(
        AUDIT_DIR / "unresolved_aircraft.csv",
        [
            "bts_code",
            "manufacturer",
            "description",
            "long_name",
            "short_name",
        ],
        missing_aircraft,
    )

    print("\nAuditing BTS flight coverage...")

    coverage = audit_t100_coverage(
        airlines,
        aircraft,
    )

    total = coverage.get("total_departures", 0)
    mapped = coverage.get("mapped_departures", 0)

    percentage = (
        mapped / total * 100
        if total else 0
    )

    print("\nFlightEngine BTS Mapping Report")
    print("=" * 45)

    print(f"Airlines mapped: {len(airlines):,}")
    print(
        f"Airlines unresolved: "
        f"{len(missing_airlines):,}"
    )

    print(f"Aircraft mapped: {len(aircraft):,}")
    print(
        f"Aircraft unresolved: "
        f"{len(missing_aircraft):,}"
    )

    print(
        "Mapped flight rows:",
        f"{coverage.get('mapped_rows', 0):,}",
        "/",
        f"{coverage.get('total_rows', 0):,}",
    )

    print(
        f"Mapped departures: {percentage:.2f}%"
    )

    print(f"\nMappings saved to: {REFERENCE_DIR}")
    print(f"Audit reports saved to: {AUDIT_DIR}")


if __name__ == "__main__":
    main()
