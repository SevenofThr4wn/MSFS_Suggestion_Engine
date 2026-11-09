from __future__ import annotations

import os
import re
import httpx

from dataclasses import asdict, dataclass
from hashlib import sha256
from threading import Lock
from time import monotonic

from dotenv import load_dotenv


load_dotenv()

METAR_API_URL = os.getenv("METAR_API_URL")

@dataclass(frozen=True)
class WeatherContext:
    """
    Weather observations for an airport.

    Contains available METAR information and any
    warnings associated with that observation.
    """

    icao: str
    available: bool
    category: str | None = None
    wind_speed_kt: float | None = None
    visibility_mi: float | None = None
    observation_time: str | None = None
    raw: str | None = None
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        """Serialize the weather context."""
        return asdict(self)


# ============================================================
# METAR Parsing
# ============================================================

def parse_metar_json(
    icao: str,
    obj: dict,
) -> WeatherContext:
    """
    Parse a JSON METAR observation into a WeatherContext.

    Handles:
    - Flight category
    - Wind speed
    - Visibility
    - Observation time
    - Thunderstorms
    - Freezing rain
    """

    def number(value) -> float | None:
        try:
            return (
                float(value)
                if value is not None
                else None
            )
        except (TypeError, ValueError):
            return None

    raw = str(
        obj.get("rawOb") or ""
    )

    category = (
        str(obj.get("fltCat") or "").upper()
        or None
    )

    if category not in {
        "VFR",
        "MVFR",
        "IFR",
        "LIFR",
    }:
        category = None

    warnings: list[str] = []

    if re.search(
        r"\bTS\b|\b\+TS|\bTSRA\b",
        raw,
    ):
        warnings.append(
            "Thunderstorm reported in observation"
        )

    if "FZRA" in raw:
        warnings.append(
            "Freezing rain reported in observation"
        )

    return WeatherContext(
        icao=icao,
        available=True,
        category=category,
        wind_speed_kt=number(
            obj.get("wspd")
        ),
        visibility_mi=number(
            obj.get("visib")
        ),
        observation_time=(
            str(obj.get("obsTime"))
            if obj.get("obsTime") is not None
            else None
        ),
        raw=raw or None,
        warnings=tuple(warnings),
    )

class EnvironmentEngine:
    """
    Manage flight environment conditions and simulator scenarios.

    Responsibilities:
    - Retrieve live METAR observations
    - Cache weather data
    - Evaluate departure and arrival weather
    - Generate deterministic flight scenarios

    Weather information is observational and is not
    suitable for real-world flight dispatch decisions.

    Generated scenarios are simulated events and do not
    represent actual aircraft or airport conditions.
    """

    SCENARIOS = (
        (
            "normal",
            "Normal scheduled flight",
            "No scripted abnormal event",
        ),
        (
            "weather_diversion",
            "Weather diversion exercise",
            "Simulator scenario: destination weather "
            "deteriorates; consider a suitable alternate",
        ),
        (
            "technical_issue",
            "Technical systems exercise",
            "Simulator scenario: an aircraft system "
            "indicates a non-normal condition",
        ),
        (
            "medical_priority",
            "Passenger medical priority",
            "Simulator scenario: coordinate a priority "
            "arrival or diversion",
        ),
    )

    def __init__(
        self,
        ttl_seconds: int = 600,
    ) -> None:
        """
        Initialize the environment engine.

        Args:
            ttl_seconds:
                Number of seconds to retain cached
                weather observations before refreshing.
        """
        self.ttl_seconds = ttl_seconds

        self._cache: dict[
            str,
            tuple[float, WeatherContext],
        ] = {}

        self._lock = Lock()

    def fetch(
        self,
        icao_codes: list[str],
        *,
        live: bool = False,
    ) -> dict[str, WeatherContext]:
        """
        Retrieve weather observations for airport ICAO codes.

        Uses a TTL cache to reduce repeated HTTP requests.

        When live=False, returns unavailable weather contexts
        without querying the external weather provider.
        """
        codes = list(
            dict.fromkeys(
                code.strip().upper()
                for code in icao_codes
                if code
            )
        )

        if not live:
            return {
                code: WeatherContext(
                    code,
                    False,
                    warnings=(
                        "Live weather disabled",
                    ),
                )
                for code in codes
            }

        now = monotonic()

        with self._lock:
            missing = [
                code
                for code in codes
                if (
                    code not in self._cache
                    or now - self._cache[code][0]
                    >= self.ttl_seconds
                )
            ]


        if missing:
            try:
                with httpx.Client(
                    timeout=8,
                    headers={
                        "User-Agent": (
                            "MSFS-Suggestion-Engine/0.1 "
                            "(educational)"
                        )
                    },
                ) as client:
                    response = client.get(
                        METAR_API_URL,
                        params={
                            "ids": ",".join(missing[:100]),
                            "format": "json",
                        },
                    )

                    response.raise_for_status()

                    payload = (
                        response.json()
                        if response.status_code != 204
                        else []
                    )

                by_icao = {
                    str(
                        row.get("icaoId") or ""
                    ).upper(): row
                    for row in payload
                    if isinstance(row, dict)
                }

                fresh = {
                    code: (
                        parse_metar_json(
                            code,
                            by_icao[code],
                        )
                        if code in by_icao
                        else WeatherContext(
                            code,
                            False,
                            warnings=(
                                "No METAR returned",
                            ),
                        )
                    )
                    for code in missing[:100]
                }

            except (
                httpx.HTTPError,
                ValueError,
                TypeError,
            ) as exc:
                fresh = {
                    code: WeatherContext(
                        code,
                        False,
                        warnings=(
                            "Weather provider unavailable: "
                            f"{type(exc).__name__}",
                        ),
                    )
                    for code in missing[:100]
                }

            with self._lock:
                self._cache.update(
                    {
                        code: (now, item)
                        for code, item in fresh.items()
                    }
                )

        with self._lock:
            return {
                code: (
                    self._cache[code][1]
                    if code in self._cache
                    else WeatherContext(
                        code,
                        False,
                        warnings=(
                            "Not queried",
                        ),
                    )
                )
                for code in codes
            }

    @staticmethod
    def evaluate(
        departure: WeatherContext,
        arrival: WeatherContext,
    ) -> tuple[float | None, list[str]]:
        """
        Evaluate weather conditions at departure and arrival.

        Returns a score and explanatory warnings.

        A missing observation produces an unknown score
        rather than an invented weather assessment.
        """
        if (
            not departure.available
            or not arrival.available
        ):
            return (
                None,
                [
                    "Weather score unavailable; current "
                    "observations incomplete or disabled"
                ],
            )

        categories = {
            "VFR": 100,
            "MVFR": 75,
            "IFR": 45,
            "LIFR": 20,
        }

        if (
            departure.category not in categories
            or arrival.category not in categories
        ):
            return (
                None,
                [
                    "METAR flight-category data missing"
                ],
            )

        score = (
            categories[departure.category]
            + categories[arrival.category]
        ) / 2

        warnings = [
            *departure.warnings,
            *arrival.warnings,
        ]

        if warnings:
            score = min(
                score,
                40,
            )

        return (
            round(score, 2),
            warnings
            + [
                "METAR is an observation, "
                "not a forecast for arrival"
            ],
        )

    
    @classmethod
    def generate_scenario(
        cls,
        departure: str,
        arrival: str,
        aircraft_id: int,
        enabled: bool,
    ) -> dict:
        """
        Generate a deterministic flight simulation scenario.

        The generated scenario is based on:
        - Departure ICAO
        - Arrival ICAO
        - Aircraft database ID

        When scenarios are disabled, a normal flight is returned.

        When enabled, the same departure, arrival and aircraft
        combination produces the same scenario.

        Returns:
            A dictionary containing:
            - type
            - title
            - description
            - simulated
        """
        if not enabled:
            event = cls.SCENARIOS[0]

        else:
            key = (
                f"{departure}:{arrival}:{aircraft_id}"
            ).encode("utf-8")

            index = (
                int.from_bytes(
                    sha256(key).digest()[:4],
                    "big",
                )
                % len(cls.SCENARIOS)
            )

            event = cls.SCENARIOS[index]

        return {
            "type": event[0],
            "title": event[1],
            "description": event[2],
            "simulated": True,
        }
