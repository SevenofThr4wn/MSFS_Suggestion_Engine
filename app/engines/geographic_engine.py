from __future__ import annotations

import logging

from bisect import bisect_left, bisect_right
from collections import OrderedDict
from dataclasses import dataclass
from math import asin, atan2, cos, degrees, radians, sin, sqrt
from threading import Lock
from time import monotonic
from typing import Any, ClassVar

from app.core.constants import (
    EARTH_RADIUS_KM,
    KM_PER_NAUTICAL_MILE,
)
from app.providers.airport_provider import AirportProvider
from app.schemas.geographic_discovery import (
    GeographicCandidate,
    GeographicDiscoveryResponse,
)


logger = logging.getLogger("flightengine.geographic")


@dataclass(frozen=True)
class _IndexedAirport:
    icao_code: str
    iata_code: str | None
    name: str
    latitude: float
    longitude: float
    distance_nm: float


@dataclass(frozen=True)
class _OriginIndex:
    provider: Any
    latitude: float
    longitude: float
    created_at: float
    distances: tuple[float, ...]
    airports: tuple[_IndexedAirport, ...]


class GeographicEngine:
    """
    Great-circle calculations and cached geographic discovery.

    Distance indexes are shared between instances using
    the same airport provider.

    Cached indexes expire automatically and can also be
    invalidated explicitly following airport data updates.
    """

    CACHE_TTL_SECONDS: ClassVar[int] = 600
    CACHE_MAX_ORIGINS: ClassVar[int] = 16

    _cache: ClassVar[
        OrderedDict[tuple[int, str], _OriginIndex]
    ] = OrderedDict()

    _cache_lock: ClassVar[Lock] = Lock()

    _cache_hits: ClassVar[int] = 0
    _cache_misses: ClassVar[int] = 0

    def __init__(
        self,
        airport_provider: AirportProvider | None = None,
    ) -> None:
        self.provider = airport_provider

    # ========================================================
    # Geographic Calculations
    # ========================================================

    @staticmethod
    def distance_nm(
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        """Calculate great-circle distance in nautical miles."""
        phi1 = radians(lat1)
        phi2 = radians(lat2)

        delta_phi = radians(lat2 - lat1)
        delta_lambda = radians(lon2 - lon1)

        a = (
            sin(delta_phi / 2) ** 2
            + cos(phi1)
            * cos(phi2)
            * sin(delta_lambda / 2) ** 2
        )

        a = max(0.0, min(1.0, a))

        distance_km = (
            2 * EARTH_RADIUS_KM * asin(sqrt(a))
        )

        return distance_km / KM_PER_NAUTICAL_MILE

    @staticmethod
    def initial_bearing(
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        """Calculate the initial true bearing in degrees."""
        phi1 = radians(lat1)
        phi2 = radians(lat2)

        delta_lambda = radians(lon2 - lon1)

        y = sin(delta_lambda) * cos(phi2)

        x = (
            cos(phi1) * sin(phi2)
            - sin(phi1)
            * cos(phi2)
            * cos(delta_lambda)
        )

        return (degrees(atan2(y, x)) + 360) % 360

    # ========================================================
    # Provider Access
    # ========================================================

    def _require_provider(self) -> AirportProvider:
        """Return the configured airport provider."""
        if self.provider is None:
            raise RuntimeError(
                "Geographic discovery requires an AirportProvider."
            )

        return self.provider

    # ========================================================
    # Cache Management
    # ========================================================

    @classmethod
    def invalidate_cache(cls) -> None:
        """Clear all geographic distance indexes."""
        with cls._cache_lock:
            cls._cache.clear()

        logger.info("GEOGRAPHIC CACHE | invalidated")

    @classmethod
    def cache_info(cls) -> dict[str, int]:
        """Return current geographic cache statistics."""
        with cls._cache_lock:
            return {
                "hits": cls._cache_hits,
                "misses": cls._cache_misses,
                "entries": len(cls._cache),
                "max_entries": cls.CACHE_MAX_ORIGINS,
            }

    @classmethod
    def reset_cache_stats(cls) -> None:
        """Reset cache counters without removing cached data."""
        with cls._cache_lock:
            cls._cache_hits = 0
            cls._cache_misses = 0

    # ========================================================
    # Distance Index Construction
    # ========================================================

    def _build_index(
        self,
        origin: Any,
        provider: AirportProvider,
    ) -> _OriginIndex:
        """
        Build a sorted distance index for a departure airport.

        Distances are calculated once when the index is built.
        Bearings are calculated later for selected candidates.
        """
        started = monotonic()

        airports: list[_IndexedAirport] = []

        for airport in provider.list_airports():
            if airport.icao_code == origin.icao_code:
                continue

            distance = self.distance_nm(
                origin.latitude,
                origin.longitude,
                airport.latitude,
                airport.longitude,
            )

            airports.append(
                _IndexedAirport(
                    icao_code=airport.icao_code,
                    iata_code=airport.iata_code,
                    name=airport.name,
                    latitude=airport.latitude,
                    longitude=airport.longitude,
                    distance_nm=distance,
                )
            )

        airports.sort(
            key=lambda airport: (
                airport.distance_nm,
                airport.icao_code,
            )
        )

        result = _OriginIndex(
            provider=provider,
            latitude=origin.latitude,
            longitude=origin.longitude,
            created_at=monotonic(),
            distances=tuple(
                airport.distance_nm
                for airport in airports
            ),
            airports=tuple(airports),
        )

        logger.info(
            "GEOGRAPHIC INDEX | origin=%s airports=%d "
            "build_ms=%.2f",
            origin.icao_code,
            len(airports),
            (monotonic() - started) * 1000,
        )

        return result

    def _get_index(
        self,
        origin: Any,
        provider: AirportProvider,
    ) -> _OriginIndex:
        """
        Return a cached index or build a new one.

        The cache key includes provider identity and origin ICAO.
        The stored provider reference prevents accidental identity
        reuse while the entry remains cached.
        """
        key = (
            id(provider),
            origin.icao_code,
        )

        now = monotonic()

        with self._cache_lock:
            existing = self._cache.get(key)

            valid = (
                existing is not None
                and existing.provider is provider
                and existing.latitude == origin.latitude
                and existing.longitude == origin.longitude
                and (
                    now - existing.created_at
                    < self.CACHE_TTL_SECONDS
                )
            )

            if valid:
                type(self)._cache_hits += 1
                self._cache.move_to_end(key)

                logger.debug(
                    "GEOGRAPHIC CACHE HIT | origin=%s",
                    origin.icao_code,
                )

                return existing

            type(self)._cache_misses += 1

        # Build outside the lock so other cached origins
        # remain accessible during index construction.
        index = self._build_index(
            origin,
            provider,
        )

        with self._cache_lock:
            # A concurrent request may have populated the
            # same key while this index was being built.
            current = self._cache.get(key)

            if (
                current is not None
                and current.provider is provider
                and current.latitude == origin.latitude
                and current.longitude == origin.longitude
                and (
                    monotonic() - current.created_at
                    < self.CACHE_TTL_SECONDS
                )
            ):
                self._cache.move_to_end(key)
                return current

            self._cache[key] = index
            self._cache.move_to_end(key)

            while len(self._cache) > self.CACHE_MAX_ORIGINS:
                self._cache.popitem(last=False)

        return index

    # ========================================================
    # Geographic Discovery
    # ========================================================

    def discover(
        self,
        departure_code: str,
        *,
        min_distance_nm: float = 100,
        max_distance_nm: float = 3000,
        limit: int = 100,
    ) -> GeographicDiscoveryResponse:
        """
        Find airports within a great-circle distance range.

        Uses a cached sorted distance index and binary search
        to avoid repeatedly scanning the full airport catalog.

        Result ordering and candidate distribution follow
        the original geographic discovery implementation.
        """
        if min_distance_nm < 0:
            raise ValueError(
                "Minimum distance cannot be negative."
            )

        if max_distance_nm <= min_distance_nm:
            raise ValueError(
                "Maximum distance must exceed minimum distance."
            )

        if limit < 1:
            raise ValueError(
                "Candidate limit must be at least 1."
            )

        started = monotonic()

        provider = self._require_provider()

        origin = provider.get_by_code(
            departure_code.strip().upper()
        )

        if origin is None:
            raise LookupError(
                f"Departure airport not found: {departure_code}"
            )

        index = self._get_index(
            origin,
            provider,
        )

        # ----------------------------------------------------
        # Binary Search for the Requested Distance Window
        # ----------------------------------------------------

        start = bisect_left(
            index.distances,
            min_distance_nm,
        )

        end = bisect_right(
            index.distances,
            max_distance_nm,
        )

        # ----------------------------------------------------
        # Construct Matching Candidates
        # ----------------------------------------------------

        matches: list[GeographicCandidate] = []

        for airport in index.airports[start:end]:
            bearing = self.initial_bearing(
                origin.latitude,
                origin.longitude,
                airport.latitude,
                airport.longitude,
            )

            matches.append(
                GeographicCandidate(
                    icao_code=airport.icao_code,
                    iata_code=airport.iata_code,
                    name=airport.name,
                    distance_nm=round(
                        airport.distance_nm,
                        2,
                    ),
                    initial_bearing_deg=round(
                        bearing,
                        2,
                    ),
                )
            )

        # Preserve the original rounded-distance ordering.
        matches.sort(
            key=lambda airport: (
                airport.distance_nm,
                airport.icao_code,
            )
        )

        total_matches = len(matches)

        # ----------------------------------------------------
        # Candidate Distribution
        # ----------------------------------------------------

        if len(matches) > limit:
            if limit == 1:
                matches = [
                    matches[len(matches) // 2]
                ]
            else:
                indices = [
                    (
                        i * (len(matches) - 1)
                    ) // (limit - 1)
                    for i in range(limit)
                ]

                matches = [
                    matches[index]
                    for index in indices
                ]

        elapsed_ms = (
            monotonic() - started
        ) * 1000

        logger.info(
            "GEOGRAPHIC DISCOVERY | origin=%s "
            "matches=%d returned=%d elapsed_ms=%.2f",
            origin.icao_code,
            total_matches,
            len(matches),
            elapsed_ms,
        )

        return GeographicDiscoveryResponse(
            departure_code=origin.icao_code,
            total_matches=total_matches,
            candidates=matches,
        )
