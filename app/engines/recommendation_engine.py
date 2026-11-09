from __future__ import annotations

import os
import logging
import time
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engines.decision_trace import DecisionTrace
from app.engines.environment_engine import EnvironmentEngine
from app.engines.airport_engine import AirportEngine
from app.engines.history_engine import HistoryEngine
from app.engines.operations_engine import OperationsEngine
from app.engines.route_engine import RouteEngine

from app.db.models.aircraft import Aircraft

from app.schemas.recommendation import (
    RecommendationRequest,
    RecommendationResponse,
    ScoredRecommendation,
)
from app.schemas.route import RouteRecommendationRequest

logger = logging.getLogger("flightengine.recommendations.engine")


class RecommendationEngine:
    def __init__(
        self,
        session: Session,
        route_engine: RouteEngine,
        environment: EnvironmentEngine,
    ):
        self.session = session
        self.route_engine = route_engine
        self.environment = environment

        self.operations = OperationsEngine(session)
        self.history = HistoryEngine(session)

        self.airport_engine = AirportEngine(
            gate_inventory_path=(
                os.getenv("MSFS_GATE_INVENTORY") or None
            ),
        )

        self.catalog = getattr(
            route_engine,
            "catalog",
            None,
        )

    def recommend(
        self,
        request: RecommendationRequest,
    ) -> RecommendationResponse:
        trace = DecisionTrace()
        request_id = str(trace.request_id)
        started = time.perf_counter()
        outcomes = Counter()

        def event(stage: str, message: str, *values) -> None:
            logger.info("[%s] %-12s | " + message, request_id, stage, *values)

        def skip(route, reason: str, detail: str = "") -> None:
            outcomes[reason] += 1
            event(
                "SKIP",
                "%s -> %s | aircraft_id=%s | %s%s",
                route.departure_icao,
                route.arrival_icao,
                route.aircraft_id,
                reason,
                f" | {detail}" if detail else "",
            )

        event(
            "START",
            "departure=%s | arrival=%s | category=%s | mode=%s | limit=%s | duration=%s-%sh | min_replayability=%s",
            request.departure_code,
            request.arrival_code or "ANY",
            request.preferred_category or "ANY",
            request.airport_mode,
            request.limit,
            request.min_duration_hours,
            request.max_duration_hours,
            request.min_flyability_score,
        )

        trace.record(
            "request",
            "received",
            details={
                "mode": str(request.mode),
                "limit": request.limit,
                "departure": request.departure_code,
            },
        )

        rejected_examples = []

        # --------------------------------------------------
        # Route Discovery
        # --------------------------------------------------

        # Ask the existing engine for a larger shortlist.
        # The RouteEngine caps the limit at 50.
        pool_size = min(
            50,
            max(request.limit * 5, request.limit),
        )

        route_request = RouteRecommendationRequest.model_validate(
            {
                **request.model_dump(
                    exclude={
                        "live_weather",
                        "scenarios_enabled",
                        "require_real_world_service",
                        "strict_aircraft_category",
                        "weather_preference",
                        "include_decision_trace",
                        "include_rejected_examples",
                        "departure_gate_enabled",
                    }
                ),
                "limit": pool_size,
            }
        )

        event("DISCOVERY", "Calling RouteEngine | shortlist_limit=%d", pool_size)
        route_response = self.route_engine.recommend(
            route_request
        )

        routes = list(
            route_response.recommendations
        )
        event(
            "DISCOVERY",
            "generated_candidates=%d | shortlisted=%d (only shortlisted routes are evaluated here)",
            route_response.total_candidates,
            len(routes),
        )

        trace.record(
            "route_discovery",
            "completed",
            details={
                "candidates": route_response.total_candidates,
                "returned": len(routes),
            },
        )

        # --------------------------------------------------
        # Aircraft Reference Loading
        # --------------------------------------------------

        aircraft_ids = {
            route.aircraft_id
            for route in routes
        }

        aircraft_map = {
            aircraft.id: aircraft
            for aircraft in self.session.scalars(
                select(Aircraft).where(
                    Aircraft.id.in_(aircraft_ids)
                )
            ).all()
        }

        # --------------------------------------------------
        # Strict Aircraft Category Filtering
        # --------------------------------------------------

        if (
            request.preferred_category
            and request.strict_aircraft_category
            and routes
        ):
            ids = {
                route.aircraft_id
                for route in routes
            }

            matching = set(
                self.session.scalars(
                    select(Aircraft.id).where(
                        Aircraft.id.in_(ids),
                        Aircraft.category == request.preferred_category,
                    )
                ).all()
            )

            retained = []
            for route in routes:
                if route.aircraft_id not in matching:
                    skip(
                        route,
                        "AIRCRAFT_CATEGORY",
                        f"required={request.preferred_category}",
                    )
                else:
                    retained.append(route)
            routes = retained
            event("FILTER", "After aircraft-category filter | remaining=%d", len(routes))

        # --------------------------------------------------
        # Supporting Engine Evaluations
        # --------------------------------------------------

        route_dicts = [
            route.model_dump()
            for route in routes
        ]

        ops = self.operations.evaluate_many(
            route_dicts
        )

        novelty = self.history.evaluate_many(
            route_dicts
        )

        airport_codes = [
            code
            for route in routes
            for code in (
                route.departure_icao,
                route.arrival_icao,
            )
        ]

        event("ENRICHMENT", "Evaluating operations/history | shortlisted=%d", len(routes))
        event("WEATHER", "Fetching weather | unique_airports=%d | live=%s", len(set(airport_codes)), request.live_weather)
        weather = self.environment.fetch(
            airport_codes,
            live=request.live_weather,
        )

        enriched = []

        # --------------------------------------------------
        # Route Validation and Scoring
        # --------------------------------------------------

        event("EVALUATION", "Starting suitability/scoring loop | routes=%d", len(routes))
        for index, (route, operation, (
            novelty_score,
            novelty_notes,
        )) in enumerate(zip(routes, ops, novelty), start=1):
            event(
                "AIRPORT",
                "[%d/%d] %s -> %s | aircraft_id=%s | aircraft=%s | distance_nm=%.1f | duration_min=%s | base_score=%.2f | replayability=%.2f",
                index,
                len(routes),
                route.departure_icao,
                route.arrival_icao,
                route.aircraft_id,
                route.aircraft_name,
                route.distance_nm,
                route.estimated_duration_min,
                route.score,
                route.flyability_score,
            )
            aircraft = aircraft_map.get(
                route.aircraft_id
            )

            dep = (
                self.catalog.get_by_code(
                    route.departure_icao
                )
                if self.catalog
                else None
            )

            arr = (
                self.catalog.get_by_code(
                    route.arrival_icao
                )
                if self.catalog
                else None
            )

            # ----------------------------------------------
            # Reference Data Validation
            # ----------------------------------------------

            if (
                aircraft is None
                or dep is None
                or arr is None
            ):
                trace.record(
                    "validation",
                    "reject",
                    code="MISSING_REFERENCE",
                    details={
                        "route": (
                            f"{route.departure_icao}-"
                            f"{route.arrival_icao}"
                        ),
                    },
                )

                missing = ",".join(
                    name for name, value in (
                        ("aircraft", aircraft), ("departure", dep), ("arrival", arr)
                    ) if value is None
                )
                skip(route, "MISSING_REFERENCE", f"missing={missing}")
                continue

            # ----------------------------------------------
            # Aircraft and Airport Suitability
            # ----------------------------------------------

            validation = self.airport_engine.validate_route(
                aircraft,
                dep,
                arr,
                route.distance_nm,
            )

            trace.record(
                "validation",
                validation.status,
                details={
                    "route": (
                        f"{route.departure_icao}-"
                        f"{route.arrival_icao}"
                    ),
                    "aircraft_id": aircraft.id,
                    "issues": [
                        issue.to_dict()
                        for issue in validation.issues
                    ],
                },
            )

            issue_descriptions = [
                f"{issue.code}: {issue.message}"
                for issue in validation.issues
            ]
            event(
                "VALIDATION",
                "%s -> %s | aircraft=%s | status=%s | issues=%d%s",
                route.departure_icao,
                route.arrival_icao,
                aircraft.display_name,
                validation.status,
                len(validation.issues),
                f" | reasons={'; '.join(issue_descriptions)}" if issue_descriptions else "",
            )

            if validation.status == "rejected":
                if (
                    request.include_rejected_examples
                    and len(rejected_examples) < 20
                ):
                    rejected_examples.append(
                        {
                            "departure_icao": dep.icao_code,
                            "arrival_icao": arr.icao_code,
                            "aircraft_id": aircraft.id,
                            **validation.to_dict(),
                        }
                    )

                skip(route, "RUNWAY_OR_AIRCRAFT_REJECTED", "; ".join(issue_descriptions))
                continue

            if (
                validation.status == "indeterminate"
                and not request.include_indeterminate
            ):
                skip(route, "INDETERMINATE_VALIDATION", "; ".join(issue_descriptions))
                continue

            # ----------------------------------------------
            # Real-World Service Filtering
            # ----------------------------------------------

            verified_service = bool(
                operation.verified_catalog_match
            )

            route = route.model_copy(
                update={
                    "is_real_world_route": verified_service
                }
            )

            trace.record(
                "operations",
                "verified" if verified_service else "unverified",
                details={
                    "departure": route.departure_icao,
                    "arrival": route.arrival_icao,
                    "aircraft_id": route.aircraft_id,
                    "verified_catalog_match": verified_service,
                },
            )

            if (
                request.require_real_world_service
                and not verified_service
            ):
                skip(route, "UNVERIFIED_REAL_WORLD_SERVICE")
                continue

            # ----------------------------------------------
            # Flyability Filtering
            # ----------------------------------------------

            flyability = route.flyability_score

            if flyability < request.min_flyability_score:
                trace.record(
                    "replayability",
                    "filtered",
                    code="LOW_REPLAYABILITY",
                    details={
                        "route": (
                            f"{route.departure_icao}-"
                            f"{route.arrival_icao}"
                        ),
                        "aircraft_id": route.aircraft_id,
                        "score": flyability,
                        "minimum": request.min_flyability_score
                    }
                )
                skip(route, "LOW_REPLAYABILITY", f"score={flyability:.2f} | minimum={request.min_flyability_score:.2f}")
                continue

            # ----------------------------------------------
            # Weather Evaluation
            # ----------------------------------------------

            departure_wx = weather[
                route.departure_icao
            ]

            arrival_wx = weather[
                route.arrival_icao
            ]

            weather_score, weather_notes = (
                self.environment.evaluate(
                    departure_wx,
                    arrival_wx,
                )
            )

            if (
                request.weather_preference == "challenging"
                and weather_score is not None
            ):
                weather_match = 100 - weather_score

            elif (
                request.weather_preference == "fair"
                and weather_score is not None
            ):
                weather_match = weather_score

            else:
                weather_match = 50.0

            # Unknown weather and realism information
            # are neutral in ranking and never represented
            # as verified evidence.
            effective_realism = (
                operation.score
                if operation.score is not None
                else 50.0
            )

            # ----------------------------------------------
            # Weighted Recommendation Scoring
            # ----------------------------------------------

            preference_score = route.score

            breakdown = {
                "preference": round(
                    preference_score * 0.35,
                    2,
                ),
                "flyability": round(
                    flyability * 0.35,
                    2,
                ),
                "realism": round(
                    effective_realism * 0.15,
                    2,
                ),
                "novelty": round(
                    novelty_score * 0.10,
                    2,
                ),
                "weather_match": round(
                    weather_match * 0.05,
                    2,
                ),
            }

            final_score = round(
                sum(breakdown.values()),
                2,
            )
            event(
                "SCORE",
                "%s -> %s | aircraft=%s | preference=%.2f | replayability=%.2f | realism=%s | novelty=%.2f | weather=%s | weather_match=%.2f | final=%.2f",
                route.departure_icao,
                route.arrival_icao,
                aircraft.display_name,
                preference_score,
                flyability,
                f"{operation.score:.2f}" if operation.score is not None else "UNKNOWN(neutral=50)",
                novelty_score,
                f"{weather_score:.2f}" if weather_score is not None else "UNKNOWN",
                weather_match,
                final_score,
            )
            logger.debug("[%s] BREAKDOWN | %s -> %s | %s", request_id, route.departure_icao, route.arrival_icao, breakdown)

            # ----------------------------------------------
            # Scenario Generation
            # ----------------------------------------------

            scenario = self.environment.generate_scenario(
                departure=route.departure_icao,
                arrival=route.arrival_icao,
                aircraft_id=route.aircraft_id,
                enabled=request.scenarios_enabled,
            )

            # ----------------------------------------------
            # Warning Aggregation
            # ----------------------------------------------

            warning_set = list(
                dict.fromkeys(
                    [
                        *route.warnings,
                        *weather_notes,
                        *operation.notes,
                        *novelty_notes,
                        (
                            "Screening scores are simulator heuristics, "
                            "not dispatch/safety certification"
                        ),
                    ]
                )
            )

            # ----------------------------------------------
            # Departure Gate Assignment
            # ----------------------------------------------

            gate = (
                self.airport_engine.suggest_gate(
                    airport_icao=dep.icao_code,
                    aircraft=aircraft,
                )
                if request.departure_gate_enabled
                else None
            )

            # ----------------------------------------------
            # Build Scored Recommendation
            # ----------------------------------------------

            outcomes["SCORED"] += 1
            enriched.append(
                ScoredRecommendation(
                    route=route,
                    aircraft_validation=validation.to_dict(),
                    departure_gate=(
                        gate.to_dict()
                        if gate
                        else {"status": "disabled"}
                    ),
                    flyability_score=flyability,
                    preference_score=preference_score,
                    realism_score=operation.score,
                    history_novelty_score=novelty_score,
                    weather_score=weather_score,
                    final_score=final_score,
                    score_breakdown=breakdown,
                    evidence_coverage={
                        "flyability": any(
                            route.flyability_evidence.values()
                        ),
                        "personal_replayability": (
                            route.personal_feedback_available
                        ),
                        "realism": operation.score is not None,
                        "weather": weather_score is not None,
                        "flight_history": True,
                    },
                    realism=operation.to_dict(),
                    weather={
                        "departure": departure_wx.to_dict(),
                        "arrival": arrival_wx.to_dict(),
                    },
                    scenario=scenario,
                    reasons=list(
                        dict.fromkeys(
                            [
                                *route.reasons,
                                *operation.notes,
                            ]
                        )
                    ),
                    warnings=warning_set,
                )
            )

        # --------------------------------------------------
        # Recommendation Ranking
        # --------------------------------------------------

        event("RANKING", "Scored eligible routes=%d | starting ranking/diversity", len(enriched))
        enriched.sort(
            key=lambda recommendation: (
                (
                    0
                    if recommendation.route.suitability
                    == "preliminary_pass"
                    else 1
                ),
                -recommendation.final_score,
                -recommendation.flyability_score,
                recommendation.route.departure_icao,
                recommendation.route.arrival_icao,
                recommendation.route.aircraft_id,
            )
        )

        # --------------------------------------------------
        # Aircraft Diversity Selection
        # --------------------------------------------------

        # Round-robin among aircraft to encourage
        # actual aircraft diversity.
        grouped: dict[
            int,
            list[ScoredRecommendation],
        ] = {}

        for item in enriched:
            grouped.setdefault(
                item.route.aircraft_id,
                [],
            ).append(item)

        selected = []
        seen_pairs = set()

        while (
            len(selected) < request.limit
            and any(grouped.values())
        ):
            made_progress = False

            for aircraft_id in sorted(
                grouped,
                key=lambda key: (
                    -grouped[key][0].final_score
                    if grouped[key]
                    else float("-inf")
                ),
            ):
                while grouped[aircraft_id]:
                    item = grouped[aircraft_id].pop(0)

                    pair = (
                        item.route.departure_icao,
                        item.route.arrival_icao,
                    )

                    if pair in seen_pairs:
                        outcomes["DUPLICATE_PAIR"] += 1
                        logger.debug("[%s] DIVERSITY | skip duplicate airport pair %s -> %s", request_id, *pair)
                        continue

                    event(
                        "SELECT",
                        "rank=%d | %s -> %s | aircraft=%s | score=%.2f | replayability=%.2f",
                        len(selected) + 1,
                        item.route.departure_icao,
                        item.route.arrival_icao,
                        item.route.aircraft_name,
                        item.final_score,
                        item.flyability_score,
                    )
                    selected.append(item)
                    seen_pairs.add(pair)

                    made_progress = True
                    break

                if len(selected) >= request.limit:
                    break

            if not made_progress:
                break

        # --------------------------------------------------
        # Final Decision Trace
        # --------------------------------------------------

        trace.record(
            "ranking",
            "completed",
            details={
                "eligible": len(enriched),
                "selected": len(selected),
            },
        )

        # --------------------------------------------------
        # Build API Response
        # --------------------------------------------------

        event(
            "SUMMARY",
            "generated=%d | shortlist=%d | eligible=%d | returned=%d | rejections=%s | elapsed_s=%.3f",
            route_response.total_candidates,
            len(route_response.recommendations),
            len(enriched),
            len(selected),
            dict(outcomes),
            time.perf_counter() - started,
        )

        return RecommendationResponse(
            request_id=trace.request_id,
            decision_trace=(
                trace.to_dict()
                if request.include_decision_trace
                else None
            ),
            rejected_examples=rejected_examples,
            generated_candidates=route_response.total_candidates,
            evaluated_routes=len(
                route_response.recommendations
            ),
            eligible_after_filters=len(enriched),
            returned=len(selected),
            recommendations=selected,
            warnings=(
                [
                    "Live METAR is observational and may not "
                    "describe conditions at flight arrival"
                ]
                if request.live_weather
                else []
            ),
        )
