from dataclasses import dataclass

import time
import logging

from math import ceil

from app.core.logging import get_logger

from app.db.repositories.route_catalog_repository import (
    RouteCatalogRepository,
)

from app.engines.aircraft_engine import AircraftEngine
from app.engines.airport_engine import AirportEngine, SuitabilityStatus
from app.engines.flyability_engine import FlyabilityEngine
from app.engines.geographic_engine import GeographicEngine

from app.db.models.aircraft import Aircraft
from app.db.models.route_catalog import RouteCatalogEntry

from app.providers.airport_catalog import (
    AirportCatalog,
    AirportRecord,
)

from app.schemas.aircraft import AircraftEvaluationRequest
from app.schemas.route import (
    RouteMode,
    RouteRecommendation,
    RouteRecommendationRequest,
    RouteRecommendationResponse,
    RouteStatus,
)


logger = get_logger("route_engine")


@dataclass(frozen=True)
class RouteCandidate:
    departure: AirportRecord
    arrival: AirportRecord
    aircraft: Aircraft
    route: RouteCatalogEntry | None = None

@dataclass(frozen=True)
class DurationEstimate:
    """Estimated flight and block time for a route."""

    air_time_min: int
    block_time_min: int
    cruise_distance_nm: float
    source: str = "simplified_aircraft_performance"

class RouteEngine:
    """
    Generates and evaluates flight route recommendations.

    Responsibilities:
    - Load eligible aircraft.
    - Generate database or geographic route candidates.
    - Validate airport and aircraft suitability.
    - Estimate route distance and duration.
    - Evaluate estimated flight replayability.
    - Apply route preference scoring.
    - Rank and diversify recommendations.

    Real-world route verification remains dependent on
    existing route catalog evidence.

    This engine does not independently verify airline
    schedules or assign aircraft registrations.
    """

    DISTANCE_ALLOWANCE = 0.15
    AIRCRAFT_RANGE_RESERVE = 1.10
    MAX_RECOMMENDATIONS_PER_PAIR = 2

    def __init__(
        self,
        repository: RouteCatalogRepository,
        airport_catalog: AirportCatalog,
    ):
        self.repository = repository
        self.catalog = airport_catalog

        self.aircraft_engine = AircraftEngine(repository=None)
        self.flyability_engine = FlyabilityEngine()
        self.airport_engine = AirportEngine()

        self.geographic_engine = GeographicEngine(
            airport_provider=airport_catalog.airports,
        )


    @staticmethod
    def _issues_text(assessment) -> str:
        """Use actual airport-suitability warnings and issues, if exposed."""
        parts = []
        for item in (getattr(assessment, "issues", None) or []):
            parts.append(str(getattr(item, "message", item)))
        for warning in (getattr(assessment, "warnings", None) or []):
            parts.append(str(warning))
        return "; ".join(parts) if parts else "No additional detail supplied"


    @staticmethod
    def _reject_candidate(
        candidate: RouteCandidate,
        reason: str,
        **values,
    ) -> None:
        """Log and reject a route candidate."""
        if logger.isEnabledFor(logging.DEBUG):
            details = " ".join(
                f"{key}={value}"
                for key, value in values.items()
            )

            logger.debug(
                f"EVALUATE REJECT | "
                f"{candidate.departure.icao_code} -> "
                f"{candidate.arrival.icao_code} "
                f"aircraft={candidate.aircraft.display_name} "
                f"reason={reason}"
                f"{' | ' + details if details else ''}"
            )

        return None

    @staticmethod
    def _discovery_skip(origin, destination, aircraft, reason: str, **values):
        details = " ".join(f"{key}={value}" for key, value in values.items())
        logger.info(
            "DISCOVERY SKIP | %s -> %s | aircraft=%s | reason=%s%s",
            origin.icao_code,
            destination.icao_code if destination is not None else "N/A",
            aircraft.display_name,
            reason,
            f" | {details}" if details else "",
        )

    
    # ========================================================
    # Route Preference Scoring
    # ========================================================

    @staticmethod
    def score_route(
        request: RouteRecommendationRequest,
        aircraft: Aircraft,
        departure: AirportRecord,
        arrival: AirportRecord,
        duration_min: int,
        is_real_world_route: bool,
    ) -> tuple[float, dict[str, float], list[str]]:
        """
        Calculate the preference score for a flight route.

        Scoring breakdown:
            Aircraft preference: 25 points
            Duration preference: 30 points
            Airport scenery: 20 points
            Route realism: 25 points

        Maximum score: 100 points.

        This evaluates user preferences and route evidence,
        not flight safety or aircraft operational approval.

        Args:
            request:
                Route recommendation preferences.

            aircraft:
                Aircraft assigned to the candidate route.

            departure:
                Departure airport record.

            arrival:
                Arrival airport record.

            duration_min:
                Estimated flight duration in minutes.

            is_real_world_route:
                Whether the local route catalog records
                this route as a real-world service.

        Returns:
            A tuple containing:
                - Total preference score
                - Individual scoring components
                - Human-readable ranking reasons
        """
        breakdown: dict[str, float] = {}
        reasons: list[str] = []

        # ----------------------------------------------------
        # Aircraft Preference — 25 Points
        # ----------------------------------------------------

        if request.preferred_category:
            aircraft_points = (
                25.0
                if aircraft.category == request.preferred_category
                else 0.0
            )
        else:
            aircraft_points = 25.0

        breakdown["aircraft_match"] = aircraft_points

        if request.preferred_category and aircraft_points:
            reasons.append(
                "Matches preferred aircraft category"
            )

        # ----------------------------------------------------
        # Duration Preference — 30 Points
        # ----------------------------------------------------

        duration_hours = duration_min / 60

        target_duration = (
            request.min_duration_hours
            + request.max_duration_hours
        ) / 2

        half_range = max(
            (
                request.max_duration_hours
                - request.min_duration_hours
            ) / 2,
            0.5,
        )

        deviation = abs(
            duration_hours - target_duration
        )

        duration_points = 30 * max(
            0.0,
            1 - deviation / half_range,
        )

        breakdown["duration_match"] = round(
            duration_points,
            2,
        )

        # ----------------------------------------------------
        # Airport Scenery Preference — 20 Points
        # ----------------------------------------------------

        addon_count = sum([
            departure.has_addon_scenery,
            arrival.has_addon_scenery,
        ])

        if request.prefer_addon_scenery:
            scenery_points = addon_count * 10
        else:
            scenery_points = 20.0

        breakdown["scenery_match"] = scenery_points

        if (
            request.prefer_addon_scenery
            and addon_count
        ):
            reasons.append(
                f"{addon_count} airport(s) have add-on scenery"
            )

        # ----------------------------------------------------
        # Real-World Route Evidence — 25 Points
        # ----------------------------------------------------

        realism_points = (
            25.0 if is_real_world_route else 0.0
        )

        breakdown["route_realism"] = realism_points

        if is_real_world_route:
            reasons.append(
                "Route is recorded as a real-world service"
            )

        # ----------------------------------------------------
        # Final Preference Score
        # ----------------------------------------------------

        total_score = round(
            sum(breakdown.values()),
            2,
        )

        return (
            total_score,
            breakdown,
            reasons,
        )

    # --------------------------------------------------
    # Aircraft selection
    # --------------------------------------------------

    def _get_eligible_aircraft(
        self,
        request: RouteRecommendationRequest,
    ) -> list[Aircraft]:
        aircraft_list = self.repository.list_aircraft(
            owned_only=request.owned_only,
            aircraft_id=request.aircraft_id,
        )

        if request.preferred_category:
            category = request.preferred_category.lower()

            aircraft_list = [
                aircraft
                for aircraft in aircraft_list
                if (aircraft.category or "").lower() == category
            ]

        return aircraft_list

    # --------------------------------------------------
    # Airport helpers
    # --------------------------------------------------

    def _normalize_code(self, code: str) -> str:
        normalized = code.strip().upper()
        airport = self.catalog.get_by_code(normalized)

        return (
            airport.icao_code
            if airport is not None
            else normalized
        )

    def assess_airport(
        self,
        airport: AirportRecord,
        aircraft: Aircraft,
        operation: str,
        request: RouteRecommendationRequest,
    ):
        options = request.airport_filter

        return self.airport_engine.evaluate(
            airport=airport,
            aircraft=aircraft,
            operation=operation,
            minimum_airport_size=options.minimum_airport_size,
            require_paved_runway=options.require_paved_runway,
            require_known_runway_data=(
                options.require_known_runway_data
            ),
            require_scheduled_service=(
                options.require_scheduled_service
            ),
        )

    # --------------------------------------------------
    # Candidate generation
    # --------------------------------------------------

    def generate_candidates(
        self,
        request: RouteRecommendationRequest,
    ) -> list[RouteCandidate]:
        aircraft_list = self._get_eligible_aircraft(request)

        logger.info(
            "AIRCRAFT | eligible=%d category=%s owned_only=%s requested_id=%s",
            len(aircraft_list), request.preferred_category or "any",
            request.owned_only, request.aircraft_id,
        )
        if not aircraft_list:
            logger.warning("DISCOVERY | No eligible aircraft found")
            return []

        if request.mode == RouteMode.DATABASE:
            return self._generate_database_candidates(
                request,
                aircraft_list,
            )

        if request.mode == RouteMode.DISCOVERY:
            return self.generate_geographic_candidates(
                request,
                aircraft_list,
            )

        raise ValueError(
            f"Unsupported route mode: {request.mode}"
        )

    def _generate_database_candidates(
        self,
        request: RouteRecommendationRequest,
        aircraft_list: list[Aircraft],
    ) -> list[RouteCandidate]:
        routes = self.repository.list_routes(
            departure_code=(
                self._normalize_code(request.departure_code)
                if request.departure_code
                else None
            ),
            arrival_code=(
                self._normalize_code(request.arrival_code)
                if request.arrival_code
                else None
            ),
            real_world_only=request.require_real_world_route,
        )

        aircraft_by_id = {
            aircraft.id: aircraft
            for aircraft in aircraft_list
        }

        candidates: list[RouteCandidate] = []
        logger.info("DATABASE DISCOVERY | catalog_routes=%d", len(routes))

        for route in routes:
            departure = self.catalog.get_by_code(
                route.departure_icao
            )
            arrival = self.catalog.get_by_code(
                route.arrival_icao
            )

            if departure is None or arrival is None:
                logger.info("DATABASE SKIP | %s -> %s | missing airport reference", route.departure_icao, route.arrival_icao)
                continue

            if departure.icao_code == arrival.icao_code:
                logger.info("DATABASE SKIP | %s -> %s | identical airports", departure.icao_code, arrival.icao_code)
                continue

            for assigned_aircraft in route.aircraft:
                aircraft = aircraft_by_id.get(
                    assigned_aircraft.id
                )

                if aircraft is None:
                    logger.debug("DATABASE SKIP | aircraft not eligible for %s -> %s", departure.icao_code, arrival.icao_code)
                    continue

                logger.info("DATABASE ACCEPT | %s -> %s | aircraft=%s", departure.icao_code, arrival.icao_code, aircraft.display_name)
                candidates.append(
                    RouteCandidate(
                        departure=departure,
                        arrival=arrival,
                        aircraft=aircraft,
                        route=route,
                    )
                )

                if len(candidates) >= request.max_candidates:
                    logger.info("DATABASE DISCOVERY | candidate limit reached count=%d", len(candidates))
                    return candidates

        return candidates

    # --------------------------------------------------
    # Geographic discovery
    # --------------------------------------------------

    
    def generate_geographic_candidates(
        self,
        request: RouteRecommendationRequest,
        aircraft_list: list[Aircraft],
    ) -> list[RouteCandidate]:
        """
        Discover geographically plausible routes using
        aircraft-specific duration, distance and airport
        suitability constraints.

        Profiles discovery performance while keeping
        detailed candidate diagnostics at DEBUG level.
        """
        started = time.perf_counter()

        # ====================================================
        # 1. Resolve Departure and Arrival
        # ====================================================

        if not request.departure_code:
            raise ValueError(
                "Geographic discovery requires a departure airport."
            )

        origin = self.catalog.get_by_code(
            request.departure_code
        )

        if origin is None:
            raise LookupError(
                f"Unknown departure airport: "
                f"{request.departure_code}"
            )

        requested_arrival = None

        if request.arrival_code:
            requested_arrival = self.catalog.get_by_code(
                request.arrival_code
            )

            if requested_arrival is None:
                raise LookupError(
                    f"Unknown arrival airport: "
                    f"{request.arrival_code}"
                )

        candidates: list[RouteCandidate] = []
        seen: set[tuple[str, str, int]] = set()

        # ----------------------------------------------------
        # Discovery Counters
        # ----------------------------------------------------

        aircraft_processed = 0
        destinations_checked = 0
        destinations_accepted = 0

        logger.info(
            f"GEOGRAPHIC DISCOVERY START | "
            f"departure={origin.icao_code} "
            f"aircraft={len(aircraft_list)} "
            f"airport_mode={request.airport_mode} "
            f"max_candidates={request.max_candidates}"
        )

        # ====================================================
        # 2. Aircraft Discovery
        # ====================================================

        for aircraft in aircraft_list:
            aircraft_started = time.perf_counter()
            aircraft_processed += 1

            speed = aircraft.cruise_speed_kts

            # ------------------------------------------------
            # Aircraft Speed Validation
            # ------------------------------------------------

            if speed is None or speed <= 0:
                self._discovery_skip(
                    origin,
                    None,
                    aircraft,
                    "INVALID_CRUISE_SPEED",
                    speed=speed,
                )
                continue

            # ------------------------------------------------
            # Departure Airport Suitability
            # ------------------------------------------------

            departure_check = self.assess_airport(
                origin,
                aircraft,
                "takeoff",
                request,
            )

            if departure_check.status == SuitabilityStatus.FAIL:
                self._discovery_skip(
                    origin,
                    None,
                    aircraft,
                    "DEPARTURE_UNSUITABLE",
                    details=self._issues_text(
                        departure_check
                    ),
                )
                continue

            if (
                departure_check.status == SuitabilityStatus.UNKNOWN
                and not request.include_indeterminate
            ):
                self._discovery_skip(
                    origin,
                    None,
                    aircraft,
                    "DEPARTURE_DATA_UNKNOWN",
                    details=self._issues_text(
                        departure_check
                    ),
                )
                continue

            # =================================================
            # 3. Calculate Aircraft Distance Window
            # =================================================

            min_distance = self.distance_for_block_time(
                request.min_duration_hours * 60,
                speed,
            )

            max_distance = self.distance_for_block_time(
                request.max_duration_hours * 60,
                speed,
            )

            min_distance = max(
                0,
                min_distance * (1 - self.DISTANCE_ALLOWANCE),
            )

            max_distance *= (
                1 + self.DISTANCE_ALLOWANCE
            )

            # ------------------------------------------------
            # Aircraft Range Filtering
            # ------------------------------------------------

            if aircraft.range_nm is not None:
                if aircraft.range_nm <= 0:
                    self._discovery_skip(
                        origin,
                        None,
                        aircraft,
                        "INVALID_AIRCRAFT_RANGE",
                        range_nm=aircraft.range_nm,
                    )
                    continue

                max_distance = min(
                    max_distance,
                    aircraft.range_nm
                    / self.AIRCRAFT_RANGE_RESERVE,
                )

            if max_distance <= min_distance:
                self._discovery_skip(
                    origin,
                    None,
                    aircraft,
                    "EMPTY_DISTANCE_WINDOW",
                    min_nm=round(min_distance, 1),
                    max_nm=round(max_distance, 1),
                )
                continue

            # =================================================
            # 4. Discover Destination Airports
            # =================================================

            if requested_arrival is not None:
                destinations = [requested_arrival]

            else:
                discovery = self.geographic_engine.discover(
                    departure_code=origin.icao_code,
                    min_distance_nm=min_distance,
                    max_distance_nm=max_distance,
                    limit=request.max_candidates,
                )

                destinations = []

                for result in discovery.candidates:
                    airport = self.catalog.get_by_code(
                        result.icao_code
                    )

                    if airport is not None:
                        destinations.append(airport)

            logger.debug(
                f"DISCOVERY AIRCRAFT | "
                f"aircraft={aircraft.display_name} "
                f"cruise_kts={speed} "
                f"range_nm={aircraft.range_nm} "
                f"distance_window_nm="
                f"{min_distance:.1f}..{max_distance:.1f} "
                f"destinations={len(destinations)}"
            )

            # =================================================
            # 5. Evaluate Destination Airports
            # =================================================

            aircraft_checked = 0
            aircraft_accepted = 0

            for destination_index, destination in enumerate(
                destinations,
                start=1,
            ):
                destinations_checked += 1
                aircraft_checked += 1

                logger.debug(
                    f"DISCOVERY AIRPORT | "
                    f"{destination_index}/{len(destinations)} "
                    f"{origin.icao_code} -> "
                    f"{destination.icao_code} "
                    f"aircraft={aircraft.display_name}"
                )

                # --------------------------------------------
                # Reject Same-Airport Routes
                # --------------------------------------------

                if origin.icao_code == destination.icao_code:
                    self._discovery_skip(
                        origin,
                        destination,
                        aircraft,
                        "SAME_AIRPORT",
                    )
                    continue

                # --------------------------------------------
                # Airport Discovery Eligibility
                # --------------------------------------------

                if not self.airport_engine.is_eligible(
                    destination,
                    request.airport_mode,
                ):
                    self._discovery_skip(
                        origin,
                        destination,
                        aircraft,
                        "AIRPORT_MODE_FILTER",
                        mode=request.airport_mode,
                    )
                    continue

                # --------------------------------------------
                # Arrival Airport Suitability
                # --------------------------------------------

                arrival_check = self.assess_airport(
                    destination,
                    aircraft,
                    "landing",
                    request,
                )

                if arrival_check.status == SuitabilityStatus.FAIL:
                    self._discovery_skip(
                        origin,
                        destination,
                        aircraft,
                        "ARRIVAL_UNSUITABLE",
                        details=self._issues_text(
                            arrival_check
                        ),
                    )
                    continue

                if (
                    arrival_check.status == SuitabilityStatus.UNKNOWN
                    and not request.include_indeterminate
                ):
                    self._discovery_skip(
                        origin,
                        destination,
                        aircraft,
                        "ARRIVAL_DATA_UNKNOWN",
                        details=self._issues_text(
                            arrival_check
                        ),
                    )
                    continue

                # --------------------------------------------
                # Great-Circle Distance Validation
                # --------------------------------------------

                distance = self.geographic_engine.distance_nm(
                    origin.latitude,
                    origin.longitude,
                    destination.latitude,
                    destination.longitude,
                )

                if not (
                    min_distance <= distance <= max_distance
                ):
                    self._discovery_skip(
                        origin,
                        destination,
                        aircraft,
                        "DISTANCE_OUT_OF_WINDOW",
                        distance_nm=round(distance, 1),
                        min_nm=round(min_distance, 1),
                        max_nm=round(max_distance, 1),
                    )
                    continue

                # --------------------------------------------
                # Duplicate Candidate Detection
                # --------------------------------------------

                candidate_key = (
                    origin.icao_code,
                    destination.icao_code,
                    aircraft.id,
                )

                if candidate_key in seen:
                    self._discovery_skip(
                        origin,
                        destination,
                        aircraft,
                        "DUPLICATE_CANDIDATE",
                    )
                    continue

                seen.add(candidate_key)

                # ============================================
                # 6. Accept Candidate
                # ============================================

                candidates.append(
                    RouteCandidate(
                        departure=origin,
                        arrival=destination,
                        aircraft=aircraft,
                    )
                )

                aircraft_accepted += 1
                destinations_accepted += 1

                logger.debug(
                    f"DISCOVERY ACCEPT | "
                    f"{origin.icao_code} -> "
                    f"{destination.icao_code} "
                    f"aircraft={aircraft.display_name} "
                    f"distance_nm={distance:.2f} "
                    f"arrival_status={arrival_check.status}"
                )

                # --------------------------------------------
                # Candidate Limit
                # --------------------------------------------

                if len(candidates) >= request.max_candidates:
                    elapsed_ms = (
                        time.perf_counter() - started
                    ) * 1000

                    logger.info(
                        f"GEOGRAPHIC DISCOVERY COMPLETE | "
                        f"departure={origin.icao_code} "
                        f"elapsed_ms={elapsed_ms:.2f} "
                        f"aircraft_processed={aircraft_processed} "
                        f"destinations_checked={destinations_checked} "
                        f"accepted={destinations_accepted} "
                        f"limit_reached=True"
                    )

                    return candidates

            # =================================================
            # 7. Aircraft Discovery Performance
            # =================================================

            aircraft_ms = (
                time.perf_counter() - aircraft_started
            ) * 1000

            logger.debug(
                f"DISCOVERY AIRCRAFT COMPLETE | "
                f"aircraft={aircraft.display_name} "
                f"elapsed_ms={aircraft_ms:.2f} "
                f"destinations_checked={aircraft_checked} "
                f"accepted={aircraft_accepted}"
            )

        # ====================================================
        # 8. Final Performance Summary
        # ====================================================

        elapsed_ms = (
            time.perf_counter() - started
        ) * 1000

        logger.info(
            f"GEOGRAPHIC DISCOVERY COMPLETE | "
            f"departure={origin.icao_code} "
            f"elapsed_ms={elapsed_ms:.2f} "
            f"aircraft_processed={aircraft_processed} "
            f"destinations_checked={destinations_checked} "
            f"accepted={destinations_accepted} "
            f"limit_reached=False"
        )

        return candidates

    # --------------------------------------------------
    # Distance and duration
    # --------------------------------------------------

    def _calculate_distance(
        self,
        candidate: RouteCandidate,
    ) -> tuple[float, str]:
        route = candidate.route

        if (
            route is not None
            and route.distance_nm is not None
            and route.distance_nm > 0
        ):
            return route.distance_nm, "stored_route"

        distance = GeographicEngine.distance_nm(
            candidate.departure.latitude,
            candidate.departure.longitude,
            candidate.arrival.latitude,
            candidate.arrival.longitude,
        )

        return distance, "great_circle"

    def _calculate_duration(
        self,
        candidate: RouteCandidate,
        distance_nm: float,
    ) -> tuple[int, str] | None:
        route = candidate.route
        aircraft = candidate.aircraft

        if (
            route is not None
            and route.estimated_duration_min is not None
            and route.estimated_duration_min > 0
        ):
            return (
                route.estimated_duration_min,
                "stored_route",
            )

        speed = aircraft.cruise_speed_kts

        if speed is None or speed <= 0:
            return None

        estimate = self.estimate_duration(
            distance_nm=distance_nm,
            cruise_speed_kts=speed,
        )

        return estimate.block_time_min, estimate.source

    # --------------------------------------------------
    # Real-world route metadata
    # --------------------------------------------------

    @staticmethod
    def _get_real_world_metadata(
        route: RouteCatalogEntry | None,
    ) -> tuple[
        bool,
        str | None,
        str | None,
        str | None,
    ]:
        """
        Retrieve airline and flight metadata from the route catalog.

        Airline ICAO codes are returned only when provided by
        the existing airline record.
        """
        if route is None or not route.is_real_world_route:
            return False, None, None, None

        airline = route.airline

        airline_name = (
            airline.name
            if airline is not None
            else None
        )

        airline_icao = (
            getattr(airline, "icao_code", None)
            if airline is not None
            else None
        )

        return (
            True,
            airline_name,
            airline_icao,
            route.flight_number,
        )

    # --------------------------------------------------
    # Candidate evaluation
    # --------------------------------------------------

    def evaluate_candidate(
        self,
        candidate: RouteCandidate,
        request: RouteRecommendationRequest,
    ) -> RouteRecommendation | None:
        """
        Evaluate a route candidate against distance, duration,
        airport suitability, aircraft performance, flyability,
        and user preferences.

        Individual candidate diagnostics use DEBUG logging
        to minimize overhead during large recommendation runs.
        """
        departure = candidate.departure
        arrival = candidate.arrival
        aircraft = candidate.aircraft
        route = candidate.route

        logger.debug(
            f"EVALUATE START | "
            f"{departure.icao_code} -> {arrival.icao_code} "
            f"aircraft={aircraft.display_name}"
        )

        # ====================================================
        # 1. Route Distance
        # ====================================================

        distance, distance_source = self._calculate_distance(
            candidate
        )

        if distance <= 0:
            return self._reject_candidate(
                candidate,
                "INVALID_DISTANCE",
                distance_nm=distance,
            )

        # ====================================================
        # 2. Flight Duration
        # ====================================================

        duration_result = self._calculate_duration(
            candidate,
            distance,
        )

        if duration_result is None:
            return self._reject_candidate(
                candidate,
                "MISSING_DURATION_OR_SPEED",
            )

        duration, duration_source = duration_result

        if not (
            request.min_duration_hours
            <= duration / 60
            <= request.max_duration_hours
        ):
            return self._reject_candidate(
                candidate,
                "DURATION_OUT_OF_RANGE",
                duration_min=duration,
                min_h=request.min_duration_hours,
                max_h=request.max_duration_hours,
            )

        # ====================================================
        # 3. Airport Suitability
        # ====================================================

        departure_check = self.assess_airport(
            departure,
            aircraft,
            "takeoff",
            request,
        )

        arrival_check = self.assess_airport(
            arrival,
            aircraft,
            "landing",
            request,
        )

        if (
            departure_check.status == SuitabilityStatus.FAIL
            or arrival_check.status == SuitabilityStatus.FAIL
        ):
            return self._reject_candidate(
                candidate,
                "AIRPORT_SUITABILITY",
                departure_status=departure_check.status,
                departure_details=self._issues_text(
                    departure_check
                ),
                arrival_status=arrival_check.status,
                arrival_details=self._issues_text(
                    arrival_check
                ),
            )

        # ====================================================
        # 4. Aircraft Suitability
        # ====================================================

        aircraft_result = (
            self.aircraft_engine.evaluate_aircraft(
                aircraft,
                AircraftEvaluationRequest(
                    route_distance_nm=distance,
                    departure_runway_m=(
                        departure_check.selected_runway.length_m
                        if departure_check.selected_runway
                        else None
                    ),
                    arrival_runway_m=(
                        arrival_check.selected_runway.length_m
                        if arrival_check.selected_runway
                        else None
                    ),
                ),
            )
        )

        states = {
            departure_check.status.value,
            arrival_check.status.value,
            aircraft_result.suitability,
        }

        if "rejected" in states or "fail" in states:
            return self._reject_candidate(
                candidate,
                "AIRCRAFT_SUITABILITY",
                states=sorted(states),
                aircraft_warnings=getattr(
                    aircraft_result,
                    "warnings",
                    [],
                ),
            )

        uncertain_states = {
            "indeterminate",
            "unknown",
        }

        if states.intersection(uncertain_states):
            suitability = RouteStatus.INDETERMINATE

            if not request.include_indeterminate:
                return self._reject_candidate(
                    candidate,
                    "INDETERMINATE_NOT_ALLOWED",
                    states=sorted(states),
                )

        else:
            suitability = RouteStatus.PRELIMINARY_PASS

        # ====================================================
        # 5. Flyability and Replayability
        # ====================================================

        flyability = self.flyability_engine.evaluate(
            departure=departure,
            arrival=arrival,
            aircraft=aircraft,
            duration_min=duration,
        )

        if flyability.score < request.min_flyability_score:
            return self._reject_candidate(
                candidate,
                "LOW_REPLAYABILITY",
                score=flyability.score,
                minimum=request.min_flyability_score,
            )

        # ====================================================
        # 6. Real-World Route Metadata
        # ====================================================

        (
            is_real_world_route,
            airline_name,
            airline_icao,
            flight_number,
        ) = self._get_real_world_metadata(route)

        if (
            request.require_real_world_route
            and not is_real_world_route
        ):
            return self._reject_candidate(
                candidate,
                "NO_REAL_WORLD_ROUTE_EVIDENCE",
            )

        # ====================================================
        # 7. Route Preference Scoring
        # ====================================================

        score, breakdown, ranking_reasons = self.score_route(
            request=request,
            aircraft=aircraft,
            departure=departure,
            arrival=arrival,
            duration_min=duration,
            is_real_world_route=is_real_world_route,
        )

        # ====================================================
        # 8. Reasons and Warnings
        # ====================================================

        reasons = list(
            dict.fromkeys([
                *ranking_reasons,
                *flyability.reasons,
            ])
        )

        warnings = [
            "Preliminary airport and aircraft screening only.",
            *departure_check.warnings,
            *arrival_check.warnings,
            *aircraft_result.warnings,
            *flyability.warnings,
        ]

        if distance_source == "great_circle":
            warnings.append(
                "Distance does not represent an IFR route."
            )

        warnings = list(dict.fromkeys(warnings))

        # ====================================================
        # 9. Evaluation Logging
        # ====================================================

        logger.debug(
            f"EVALUATE ACCEPT | "
            f"{departure.icao_code} -> {arrival.icao_code} "
            f"aircraft={aircraft.display_name} "
            f"distance_nm={distance:.2f} "
            f"duration_min={duration} "
            f"suitability={suitability} "
            f"flyability={flyability.score:.2f} "
            f"preference={score:.2f} "
            f"duration_source={duration_source}"
        )

        logger.debug(
            f"EVALUATE BREAKDOWN | "
            f"{departure.icao_code} -> {arrival.icao_code} "
            f"aircraft={aircraft.display_name} "
            f"scores={breakdown} "
            f"reasons={reasons} "
            f"warnings={warnings}"
        )

        # ====================================================
        # 10. Final Recommendation
        # ====================================================

        return RouteRecommendation(
            route_id=route.id if route else None,

            departure_icao=departure.icao_code,
            departure_name=departure.name,
            arrival_icao=arrival.icao_code,
            arrival_name=arrival.name,

            aircraft_id=aircraft.id,
            aircraft_name=aircraft.display_name,
            aircraft_icao_code=aircraft.icao_code,

            registration=None,
            registration_verified=False,

            airline_name=airline_name,
            airline_icao=airline_icao,
            flight_number=flight_number,
            is_real_world_route=is_real_world_route,

            distance_nm=round(distance, 2),
            distance_source=distance_source,

            estimated_duration_min=duration,
            duration_source=duration_source,

            suitability=suitability,
            score=score,
            score_breakdown=breakdown,

            reasons=reasons,
            warnings=warnings,

            flyability_score=flyability.score,
            flyability_status=flyability.status,
            flyability_breakdown=flyability.breakdown,
            flyability_evidence=flyability.evidence_coverage,
            personal_feedback_available=(
                flyability.personal_feedback_available
            ),
        )


    
    # --------------------------------------------------
    # Flight Duration Estimation
    # --------------------------------------------------

    @staticmethod
    def estimate_duration(
        distance_nm: float,
        cruise_speed_kts: float,
        *,
        climb_descent_distance_nm: float = 150.0,
        climb_descent_average_kts: float = 250.0,
        ground_time_min: float = 20.0,
    ) -> DurationEstimate:
        """
        Estimate flight duration using a simplified
        aircraft performance model.

        Calculates:
        - Climb and descent time
        - Cruise time
        - Total estimated airborne time
        - Estimated block time

        Args:
            distance_nm:
                Route distance in nautical miles.

            cruise_speed_kts:
                Aircraft cruise speed in knots.

            climb_descent_distance_nm:
                Distance allocated to climb and descent.

            climb_descent_average_kts:
                Average speed during climb and descent.

            ground_time_min:
                Additional ground time in minutes.

        Returns:
            DurationEstimate containing airborne time,
            block time, cruise distance and source.
        """
        if distance_nm <= 0:
            raise ValueError(
                "Distance must be positive."
            )

        if cruise_speed_kts <= 0:
            raise ValueError(
                "Cruise speed must be positive."
            )

        if climb_descent_average_kts <= 0:
            raise ValueError(
                "Climb/descent average speed must be positive."
            )

        if climb_descent_distance_nm < 0:
            raise ValueError(
                "Climb/descent distance cannot be negative."
            )

        if ground_time_min < 0:
            raise ValueError(
                "Ground time cannot be negative."
            )

        transition_distance = min(
            distance_nm,
            climb_descent_distance_nm,
        )

        cruise_distance = max(
            0.0,
            distance_nm - transition_distance,
        )

        transition_time_hours = (
            transition_distance
            / climb_descent_average_kts
        )

        cruise_time_hours = (
            cruise_distance / cruise_speed_kts
        )

        air_time = ceil(
            (
                transition_time_hours
                + cruise_time_hours
            ) * 60
        )

        block_time = ceil(
            air_time + ground_time_min
        )

        return DurationEstimate(
            air_time_min=air_time,
            block_time_min=block_time,
            cruise_distance_nm=round(
                cruise_distance,
                2,
            ),
        )

    # --------------------------------------------------
    # Duration-to-Distance Conversion
    # --------------------------------------------------

    @staticmethod
    def distance_for_block_time(
        block_time_min: float,
        cruise_speed_kts: float,
        *,
        climb_descent_distance_nm: float = 150.0,
        climb_descent_average_kts: float = 250.0,
        ground_time_min: float = 20.0,
    ) -> float:
        """
        Estimate the distance corresponding to a target
        flight block time.

        This is the inverse of the simplified duration
        model and is used for geographic discovery.

        Args:
            block_time_min:
                Target block time in minutes.

            cruise_speed_kts:
                Aircraft cruise speed in knots.

            climb_descent_distance_nm:
                Distance allocated to climb and descent.

            climb_descent_average_kts:
                Average climb/descent speed.

            ground_time_min:
                Additional ground time in minutes.

        Returns:
            Approximate flight distance in nautical miles.
        """
        if block_time_min < 0:
            raise ValueError(
                "Block time cannot be negative."
            )

        if cruise_speed_kts <= 0:
            raise ValueError(
                "Cruise speed must be positive."
            )

        if climb_descent_average_kts <= 0:
            raise ValueError(
                "Climb/descent average speed must be positive."
            )

        if climb_descent_distance_nm < 0:
            raise ValueError(
                "Climb/descent distance cannot be negative."
            )

        if ground_time_min < 0:
            raise ValueError(
                "Ground time cannot be negative."
            )

        airborne_hours = max(
            0.0,
            (
                block_time_min - ground_time_min
            ) / 60,
        )

        transition_hours = (
            climb_descent_distance_nm
            / climb_descent_average_kts
        )

        if airborne_hours <= transition_hours:
            return (
                airborne_hours
                * climb_descent_average_kts
            )

        cruise_hours = (
            airborne_hours - transition_hours
        )

        return (
            climb_descent_distance_nm
            + cruise_hours * cruise_speed_kts
        )


    # --------------------------------------------------
    # Recommendation ranking and selection
    # --------------------------------------------------

    def recommend(
        self,
        request: RouteRecommendationRequest,
    ) -> RouteRecommendationResponse:
        """
        Generate, evaluate, rank, and select flight recommendations.

        Profiles three processing stages:
        - Candidate discovery
        - Candidate evaluation
        - Recommendation ranking and selection

        Logs execution times in milliseconds.
        """
        started = time.perf_counter()

        logger.info(
            f"ROUTE ENGINE START | mode={request.mode} "
            f"from={request.departure_code} "
            f"to={request.arrival_code or 'any'} "
            f"limit={request.limit} "
            f"max_candidates={request.max_candidates} "
            f"duration_h={request.min_duration_hours}"
            f"..{request.max_duration_hours}"
        )

        # ====================================================
        # Candidate Discovery
        # ====================================================

        discovery_started = time.perf_counter()

        candidates = self.generate_candidates(request)

        discovery_ms = (
            time.perf_counter() - discovery_started
        ) * 1000

        candidate_count = len(candidates)

        logger.info(
            f"PERF | stage=discovery "
            f"elapsed_ms={discovery_ms:.2f} "
            f"candidates={candidate_count}"
        )

        # ====================================================
        # Candidate Evaluation
        # ====================================================

        evaluation_started = time.perf_counter()

        results: list[RouteRecommendation] = []

        for index, candidate in enumerate(
            candidates,
            start=1,
        ):
            logger.debug(
                f"CANDIDATE | {index}/{candidate_count} "
                f"{candidate.departure.icao_code} -> "
                f"{candidate.arrival.icao_code} "
                f"aircraft={candidate.aircraft.display_name}"
            )

            recommendation = self.evaluate_candidate(
                candidate,
                request,
            )

            if recommendation is not None:
                results.append(recommendation)

        evaluation_ms = (
            time.perf_counter() - evaluation_started
        ) * 1000

        eligible_count = len(results)

        logger.info(
            f"PERF | stage=evaluation "
            f"elapsed_ms={evaluation_ms:.2f} "
            f"evaluated={candidate_count} "
            f"accepted={eligible_count}"
        )

        # ====================================================
        # Ranking and Selection
        # ====================================================

        ranking_started = time.perf_counter()

        suitability_priority = {
            RouteStatus.PRELIMINARY_PASS: 0,
            RouteStatus.INDETERMINATE: 1,
            RouteStatus.REJECTED: 2,
        }

        results.sort(
            key=lambda result: (
                suitability_priority[result.suitability],
                -result.flyability_score,
                -result.score,
                result.departure_icao,
                result.arrival_icao,
                result.aircraft_id,
            )
        )

        # ----------------------------------------------------
        # Route Diversity
        # ----------------------------------------------------

        selected: list[RouteRecommendation] = []

        pair_counts: dict[
            tuple[str, str],
            int,
        ] = {}

        for recommendation in results:
            pair = (
                recommendation.departure_icao,
                recommendation.arrival_icao,
            )

            if (
                pair_counts.get(pair, 0)
                >= self.MAX_RECOMMENDATIONS_PER_PAIR
            ):
                logger.debug(
                    f"RANKING SKIP | "
                    f"{recommendation.departure_icao} -> "
                    f"{recommendation.arrival_icao} "
                    f"aircraft={recommendation.aircraft_name} "
                    f"reason=PAIR_DIVERSITY_LIMIT"
                )

                continue

            selected.append(recommendation)

            pair_counts[pair] = (
                pair_counts.get(pair, 0) + 1
            )

            if len(selected) >= request.limit:
                break

        ranking_ms = (
            time.perf_counter() - ranking_started
        ) * 1000

        # ====================================================
        # Final Recommendation Logging
        # ====================================================

        for rank, item in enumerate(
            selected,
            start=1,
        ):
            logger.debug(
                f"ROUTE SELECT | rank={rank} "
                f"{item.departure_icao} -> "
                f"{item.arrival_icao} "
                f"aircraft={item.aircraft_name} "
                f"flyability={item.flyability_score:.2f} "
                f"preference={item.score:.2f}"
            )

        # ====================================================
        # Performance Summary
        # ====================================================

        total_ms = (
            time.perf_counter() - started
        ) * 1000

        returned_count = len(selected)

        logger.info(
            f"PERF | stage=ranking "
            f"elapsed_ms={ranking_ms:.2f} "
            f"eligible={eligible_count} "
            f"returned={returned_count}"
        )

        logger.info(
            f"PERF SUMMARY | "
            f"total_ms={total_ms:.2f} "
            f"discovery_ms={discovery_ms:.2f} "
            f"evaluation_ms={evaluation_ms:.2f} "
            f"ranking_ms={ranking_ms:.2f} "
            f"candidates={candidate_count} "
            f"eligible={eligible_count} "
            f"returned={returned_count}"
        )

        # ====================================================
        # Response
        # ====================================================

        return RouteRecommendationResponse(
            mode=request.mode,
            total_candidates=candidate_count,
            total_validated=candidate_count,
            total_eligible=eligible_count,
            returned=returned_count,
            recommendations=selected,
        )
