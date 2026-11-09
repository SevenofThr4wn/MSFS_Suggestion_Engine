from __future__ import annotations

from datetime import date
from typing import Iterable

from sqlalchemy.orm import Session

from app.db.repositories.schedule_repository import ScheduleRepository
from app.engines.operations_engine import OperationsEngine
from app.schemas.route import RouteRecommendation
from app.schemas.schedule import (
    AircraftMatch,
    ScheduleLookupRequest,
    ScheduleMatch,
    ScheduleStatus,
)


class RecommendationScheduleService:
    def __init__(self, session: Session) -> None:
        self.repository = ScheduleRepository(session)

    def match_routes(
        self,
        routes: Iterable[RouteRecommendation],
        departure_date: date | None,
        prefer_scheduled_aircraft: bool = True,
    ) -> list[ScheduleMatch | None]:
        route_list = list(routes)

        schedules_by_pair = {}

        for route in route_list:
            pair = (
                route.departure_icao.upper(),
                route.arrival_icao.upper(),
            )

            if pair not in schedules_by_pair:
                schedules_by_pair[pair] = (
                    self.repository.list_for_route(
                        departure_icao=pair[0],
                        arrival_icao=pair[1],
                    )
                )

        matches: list[ScheduleMatch | None] = []

        for route in route_list:
            pair = (
                route.departure_icao.upper(),
                route.arrival_icao.upper(),
            )

            engine = OperationsEngine(
                schedules=schedules_by_pair[pair],
            )

            result = engine.lookup_schedule(
                ScheduleLookupRequest(
                    departure_icao=pair[0],
                    arrival_icao=pair[1],
                    departure_date=departure_date,
                    aircraft_icao=route.aircraft_icao_code,
                    airline_icao=route.airline_icao,
                )
            )

            candidates = result.matches

            if not candidates:
                matches.append(None)
                continue

            def rank(match: ScheduleMatch) -> tuple:
                schedule = match.schedule

                date_rank = (
                    0 if match.operates_on_date is True
                    else 1 if match.operates_on_date is None
                    else 2
                )

                aircraft_rank = (
                    0 if match.aircraft_match == AircraftMatch.EXACT
                    else 1 if match.aircraft_match == AircraftMatch.UNKNOWN
                    else 2
                )

                verification_rank = {
                    ScheduleStatus.VERIFIED: 0,
                    ScheduleStatus.HISTORICAL: 1,
                    ScheduleStatus.UNVERIFIED: 2,
                    ScheduleStatus.UNKNOWN: 3,
                }[schedule.status]

                return (
                    date_rank,
                    aircraft_rank if prefer_scheduled_aircraft else 0,
                    verification_rank,
                    schedule.departure_time_local is None,
                    schedule.departure_time_local.isoformat()
                    if schedule.departure_time_local else "",
                    schedule.flight_number or "",
                )

            matches.append(
                min(candidates, key=rank)
            )

        return matches
