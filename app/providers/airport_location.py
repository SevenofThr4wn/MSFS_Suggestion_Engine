
from __future__ import annotations

from functools import lru_cache

import airportsdata
import pycountry

from app.schemas.recommendation import AirportLocation


@lru_cache(maxsize=1)
def get_airport_data() -> dict:
    """Load ICAO airport reference data once per process."""
    return airportsdata.load("ICAO")


def country_name(code: str | None) -> str | None:
    """Convert an ISO country code to its full country name."""
    if not code:
        return None

    code = code.strip().upper()

    country = pycountry.countries.get(alpha_2=code)

    return country.name if country else code


def region_name(
    subdivision: str | None,
    country_code: str | None,
) -> str | None:
    """Resolve an airport's state, province, or territory."""
    if not subdivision:
        return None

    subdivision = subdivision.strip()

    if not subdivision:
        return None

    if not country_code:
        return subdivision

    country_code = country_code.strip().upper()

    # Already a full subdivision code, e.g. US-CA.
    if subdivision.upper().startswith(f"{country_code}-"):
        region = pycountry.subdivisions.get(
            code=subdivision.upper()
        )

        return region.name if region else subdivision

    # Try abbreviated subdivision codes, e.g. CA -> US-CA.
    region = pycountry.subdivisions.get(
        code=f"{country_code}-{subdivision.upper()}"
    )

    if region:
        return region.name

    # Preserve existing full region names.
    return subdivision


@lru_cache(maxsize=4096)
def get_airport_location(icao: str) -> AirportLocation:
    """
    Resolve geographic information for an airport.

    Returns the airport's ICAO code, name, city,
    region/state/territory, country, and a formatted
    display name.

    Args:
        icao: Four-letter ICAO airport identifier.

    Returns:
        AirportLocation containing available geographic data.
    """
    code = icao.strip().upper()

    airport = get_airport_data().get(code)

    if airport is None:
        return AirportLocation(
            icao=code,
            display_name=code,
        )

    city = airport.get("city") or None
    country_code = airport.get("country") or None
    subdivision = airport.get("subd") or None

    region = region_name(
        subdivision=subdivision,
        country_code=country_code,
    )

    country = country_name(country_code)

    location_parts = []

    for part in (city, region, country):
        if not part:
            continue

        name = part.strip()

        if name and not any(
            existing.casefold() == name.casefold()
            for existing in location_parts
        ):
            location_parts.append(name)

    return AirportLocation(
        icao=code,
        airport_name=airport.get("name"),
        city=city,
        region=region,
        country=country,
        display_name=", ".join(location_parts) or code,
    )
