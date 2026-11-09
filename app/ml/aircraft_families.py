
from __future__ import annotations

# Family IDs are stable internal identifiers.
# Human-readable names are provided separately.

FAMILY_NAMES: dict[str, str] = {
    "A220": "Airbus A220",
    "A320": "Airbus A320 family",
    "A330": "Airbus A330",
    "A340": "Airbus A340",
    "A350": "Airbus A350",
    "A380": "Airbus A380",
    "B737_CLASSIC": "Boeing 737 Classic",
    "B737_NG": "Boeing 737 NG",
    "B737_MAX": "Boeing 737 MAX",
    "B747": "Boeing 747",
    "B757": "Boeing 757",
    "B767": "Boeing 767",
    "B777": "Boeing 777",
    "B787": "Boeing 787",
    "EJET": "Embraer E-Jet",
    "EJET_E2": "Embraer E-Jet E2",
    "CRJ": "Bombardier CRJ",
    "ATR": "ATR family",
    "DHC8": "De Havilland Dash 8",
    "MD80": "McDonnell Douglas MD-80",
    "MD90": "McDonnell Douglas MD-90",
    "DC10": "McDonnell Douglas DC-10",
    "MD11": "McDonnell Douglas MD-11",
    "F70_F100": "Fokker 70/100",
}


FAMILY_CODES: dict[str, tuple[str, ...]] = {
    "A220": ("BCS1", "BCS3"),
    "A320": (
        "A318", "A319", "A320", "A321",
        "A19N", "A20N", "A21N", "A21X",
    ),
    "A330": ("A332", "A333", "A338", "A339", "A337"),
    "A340": ("A342", "A343", "A345", "A346"),
    "A350": ("A359", "A35K", "A35F"),
    "A380": ("A388",),
    "B737_CLASSIC": ("B732", "B733", "B734", "B735"),
    "B737_NG": ("B736", "B737", "B738", "B739"),
    "B737_MAX": ("B37M", "B38M", "B39M", "B3XM"),
    "B747": (
        "B741", "B742", "B743", "B744",
        "B748", "B74R", "B74S",
    ),
    "B757": ("B752", "B753"),
    "B767": ("B762", "B763", "B764"),
    "B777": (
        "B772", "B773", "B77L", "B77W",
        "B778", "B779",
    ),
    "B787": ("B788", "B789", "B78X"),
    "EJET": ("E170", "E175", "E190", "E195"),
    "EJET_E2": ("E290", "E295", "E275"),
    "CRJ": ("CRJ1", "CRJ2", "CRJ7", "CRJ9", "CRJX"),
    "ATR": ("AT43", "AT45", "AT72", "AT75", "AT76"),
    "DHC8": ("DH8A", "DH8B", "DH8C", "DH8D"),
    "MD80": ("MD81", "MD82", "MD83", "MD87", "MD88"),
    "MD90": ("MD90",),
    "DC10": ("DC10",),
    "MD11": ("MD11",),
    "F70_F100": ("F70", "F100"),
}


AIRCRAFT_TO_FAMILY = {
    code: family
    for family, codes in FAMILY_CODES.items()
    for code in codes
}


def get_aircraft_family(
    aircraft_icao: str | None,
) -> str | None:
    """Return the known family ID or None."""
    if not aircraft_icao:
        return None

    return AIRCRAFT_TO_FAMILY.get(
        aircraft_icao.strip().upper()
    )


def get_family_name(family_id: str) -> str:
    """Return a readable name for a family ID."""
    return FAMILY_NAMES.get(family_id, family_id)


def validate_family_mapping() -> None:
    """Detect conflicting or missing family definitions."""
    seen: set[str] = set()

    for family, codes in FAMILY_CODES.items():
        if family not in FAMILY_NAMES:
            raise ValueError(
                f"Family has no display name: {family}"
            )

        for code in codes:
            if code in seen:
                raise ValueError(
                    f"Aircraft code assigned twice: {code}"
                )

            seen.add(code)
