
from __future__ import annotations

import logging
from collections import defaultdict
from itertools import combinations

from app.db.repositories.route_catalog_repository import (
    RouteCatalogRepository,
)
from app.engines.geographic_engine import GeographicEngine
from app.engines.route_engine import RouteCandidate, RouteEngine
from app.providers.airport_catalog import AirportCatalog
from app.schemas.route import (
    RouteMode,
    RouteRecommendationRequest,
    RouteStatus,
)


logger = logging.getLogger(__name__)


class SceneryNetworkEngine:
    """Build connections between installed MSFS scenery airports."""

    def __init__(
        self,
        repository: RouteCatalogRepository,
        airport_catalog: AirportCatalog,
    ):
        self.repository = repository
        self.catalog = airport_catalog

        self.route_engine = RouteEngine(
            repository=repository,
            airport_catalog=airport_catalog,
        )

    def generate(
        self,
        installed_codes: set[str],
        *,
        include_plausible: bool = False,
        owned_only: bool = True,
        max_distance_nm: float = 10000,
    ) -> list[dict]:
        # --------------------------------------------------
        # 1. Resolve installed airports
        # --------------------------------------------------

        airports = {}

        for code in sorted(installed_codes):
            airport = self.catalog.get_by_code(code)

            if airport is None:
                continue

            if (
                airport.latitude is None
                or airport.longitude is None
            ):
                continue

            airports[code] = airport

        if len(airports) < 2:
            return []

        # --------------------------------------------------
        # 2. Load aircraft
        # --------------------------------------------------

        aircraft = self.repository.list_aircraft(
            owned_only=owned_only,
        )

        aircraft_by_id = {
            item.id: item
            for item in aircraft
        }

        logger.info(
            "SCENERY NETWORK | airports=%d | "
            "aircraft=%d | owned_only=%s | "
            "include_plausible=%s",
            len(airports),
            len(aircraft),
            owned_only,
            include_plausible,
        )

        # --------------------------------------------------
        # 3. Load route catalog evidence
        # --------------------------------------------------

        routes_by_pair = defaultdict(list)

        routes = self.repository.list_routes(
            real_world_only=not include_plausible,
        )

        for route in routes:
            departure_code = route.departure_icao
            arrival_code = route.arrival_icao

            if (
                departure_code not in airports
                or arrival_code not in airports
                or departure_code == arrival_code
            ):
                continue

            key = tuple(sorted((
                departure_code,
                arrival_code,
            )))

            routes_by_pair[key].append(route)

        # --------------------------------------------------
        # 4. Build evaluation request
        # --------------------------------------------------

        request = RouteRecommendationRequest(
            mode=RouteMode.DATABASE,
            min_duration_hours=0,
            max_duration_hours=30,
            owned_only=owned_only,
            include_indeterminate=True,
            min_flyability_score=0,
            prefer_addon_scenery=False,
        )

        connections = []

        # --------------------------------------------------
        # 5. Evaluate installed airport pairs
        # --------------------------------------------------

        for from_code, to_code in combinations(
            sorted(airports),
            2,
        ):
            origin = airports[from_code]
            destination = airports[to_code]

            distance = GeographicEngine.distance_nm(
                origin.latitude,
                origin.longitude,
                destination.latitude,
                destination.longitude,
            )

            if not (
                0 < distance <= max_distance_nm
            ):
                continue

            key = (from_code, to_code)

            catalog_routes = routes_by_pair.get(
                key,
                [],
            )

            verified_routes = [
                route
                for route in catalog_routes
                if (
                    route.is_real_world_route
                    and route.is_active
                )
            ]

            classification = (
                "verified"
                if verified_routes
                else "plausible"
            )

            if (
                classification == "plausible"
                and not include_plausible
            ):
                continue

            # ----------------------------------------------
            # 6. Generate aircraft candidates
            # ----------------------------------------------

            candidates = []

            seen_candidates = set()

            for route in catalog_routes:
                for assigned in route.aircraft:
                    item = aircraft_by_id.get(
                        assigned.id
                    )

                    if item is None:
                        continue

                    candidate_key = (
                        route.departure_icao,
                        route.arrival_icao,
                        item.id,
                        route.id,
                    )

                    if candidate_key in seen_candidates:
                        continue

                    seen_candidates.add(candidate_key)

                    candidates.append(
                        RouteCandidate(
                            departure=airports[
                                route.departure_icao
                            ],
                            arrival=airports[
                                route.arrival_icao
                            ],
                            aircraft=item,
                            route=route,
                        )
                    )

            if include_plausible:
                for item in aircraft:
                    for departure, arrival in (
                        (origin, destination),
                        (destination, origin),
                    ):
                        candidate_key = (
                            departure.icao_code,
                            arrival.icao_code,
                            item.id,
                            None,
                        )

                        if candidate_key in seen_candidates:
                            continue

                        seen_candidates.add(candidate_key)

                        candidates.append(
                            RouteCandidate(
                                departure=departure,
                                arrival=arrival,
                                aircraft=item,
                            )
                        )

            # ----------------------------------------------
            # 7. Evaluate candidates
            # ----------------------------------------------

            evaluated = []

            for candidate in candidates:
                result = (
                    self.route_engine.evaluate_candidate(
                        candidate,
                        request,
                    )
                )

                if result is not None:
                    evaluated.append(result)

            logger.info(
                "SCENERY NETWORK | %s -> %s | "
                "distance=%.0f NM | "
                "catalog_routes=%d | "
                "verified_routes=%d | "
                "candidates=%d | "
                "accepted=%d",
                from_code,
                to_code,
                distance,
                len(catalog_routes),
                len(verified_routes),
                len(candidates),
                len(evaluated),
            )

            # Plausible routes must pass at least one
            # preliminary aircraft evaluation.
            if (
                classification == "plausible"
                and not evaluated
            ):
                continue

            # ----------------------------------------------
            # 8. Rank aircraft suggestions
            # ----------------------------------------------

            evaluated.sort(
                key=lambda result: (
                    result.suitability
                    != RouteStatus.PRELIMINARY_PASS,
                    -result.score,
                    -result.flyability_score,
                )
            )

            aircraft_suggestions = []
            seen_aircraft = set()

            for result in evaluated:
                if result.aircraft_id in seen_aircraft:
                    continue

                seen_aircraft.add(result.aircraft_id)

                aircraft_suggestions.append({
                    "id": result.aircraft_id,
                    "name": result.aircraft_name,
                    "icao": result.aircraft_icao_code,
                    "suitability": (
                        result.suitability.value
                    ),
                    "duration_min": (
                        result.estimated_duration_min
                    ),
                    "score": result.score,
                })

                if len(aircraft_suggestions) >= 5:
                    break

            # ----------------------------------------------
            # 9. Collect verified route metadata
            # ----------------------------------------------

            directions = sorted({
                (
                    route.departure_icao,
                    route.arrival_icao,
                )
                for route in verified_routes
            })

            airlines = sorted({
                route.airline.name
                for route in verified_routes
                if (
                    route.airline is not None
                    and route.airline.name
                )
            })

            # ----------------------------------------------
            # 10. Build connection response
            # ----------------------------------------------

            connections.append({
                "id": f"{from_code}-{to_code}",
                "from_icao": from_code,
                "to_icao": to_code,
                "distance_nm": round(distance, 2),
                "classification": classification,
                "verified": bool(verified_routes),
                "directions": [
                    {
                        "from": departure,
                        "to": arrival,
                    }
                    for departure, arrival in directions
                ],
                "airlines": airlines,
                "aircraft": aircraft_suggestions,
                "reasons": (
                    [
                        "Active real-world route "
                        "catalog evidence."
                    ]
                    if verified_routes
                    else [
                        "Passed preliminary aircraft "
                        "and airport feasibility screening.",
                        "No verified airline service evidence.",
                    ]
                ),
            })

        # --------------------------------------------------
        # 11. Sort connections
        # --------------------------------------------------

        connections.sort(
            key=lambda connection: (
                connection["classification"] != "verified",
                connection["distance_nm"],
                connection["id"],
            )
        )

        logger.info(
            "SCENERY NETWORK COMPLETE | "
            "airports=%d | connections=%d | "
            "verified=%d | plausible=%d",
            len(airports),
            len(connections),
            sum(
                connection["verified"]
                for connection in connections
            ),
            sum(
                not connection["verified"]
                for connection in connections
            ),
        )

        return connections
