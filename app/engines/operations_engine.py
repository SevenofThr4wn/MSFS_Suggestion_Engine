from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.logging import get_logger

from app.schemas.schedule import (
    AircraftMatch,
    FlightSchedule,
    ScheduleLookupRequest,
    ScheduleLookupResponse,
    ScheduleMatch,
    ScheduleStatus,
)

try:
    from app.db.models.route_catalog import RouteCatalogEntry
except ImportError:
    from app.db.models.route import Route as RouteCatalogEntry


logger = get_logger("operations_engine")


# ============================================================
# Operations Assessment
# ============================================================

@dataclass(frozen=True)
class OperationsAssessment:
    """Result of evaluating route realism."""

    score: float | None
    verified_catalog_match: bool
    airline: str | None
    flight_number: str | None
    notes: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


# ============================================================
# Operations Engine
# ============================================================

class OperationsEngine:
    """
    Evaluate real-world airline operations and flight schedules.

    Responsibilities:
    - Route catalog realism evaluation
    - Airline and aircraft assignment matching
    - Historical or source-backed route evidence
    - Airline schedule lookup
    - Operating date verification
    - Scheduled aircraft compatibility

    Catalog matches and schedule evidence remain separate.
    A historical catalog match does not independently
    establish a currently operating scheduled flight.
    """

    def __init__(
        self,
        session: Session | None = None,
        schedules: list[FlightSchedule] | None = None,
    ) -> None:
        """
        Initialize the operations engine.

        Args:
            session:
                Optional SQLAlchemy database session.
                Required for route realism evaluation.

            schedules:
                Optional list of source-backed airline schedules.
                Required when performing schedule lookups.
        """
        self.session = session
        self.schedules = (
            list(schedules)
            if schedules is not None
            else []
        )

    # ========================================================
    # Route Catalog Realism
    # ========================================================

    def evaluate_many(
        self,
        routes: list[dict],
    ) -> list[OperationsAssessment]:
        """
        Evaluate route and aircraft assignments against the
        application's local route catalog.

        Args:
            routes:
                Route dictionaries containing:
                - departure_icao
                - arrival_icao
                - aircraft_id

        Returns:
            One OperationsAssessment per supplied route.

        Notes:
            An existing route catalog entry is evidence of
            a recorded assignment, not confirmation of
            current scheduled service.
        """
        if not routes:
            return []

        if self.session is None:
            raise RuntimeError(
                "Route realism evaluation requires "
                "a database session."
            )

        # ----------------------------------------------------
        # Collect Unique Airport Pairs
        # ----------------------------------------------------

        pairs = {
            (
                route["departure_icao"],
                route["arrival_icao"],
            )
            for route in routes
        }

        conditions = [
            and_(
                RouteCatalogEntry.departure_icao == departure,
                RouteCatalogEntry.arrival_icao == arrival,
            )
            for departure, arrival in pairs
        ]

        # ----------------------------------------------------
        # Retrieve Route Catalog Evidence
        # ----------------------------------------------------

        entries = self.session.scalars(
            select(RouteCatalogEntry)
            .options(
                selectinload(RouteCatalogEntry.aircraft),
                selectinload(RouteCatalogEntry.airline),
            )
            .where(
                RouteCatalogEntry.is_active.is_(True),
                or_(*conditions),
            )
        ).all()

        # ----------------------------------------------------
        # Group Records by Route
        # ----------------------------------------------------

        by_pair: dict[
            tuple[str, str],
            list[RouteCatalogEntry],
        ] = {}

        for entry in entries:
            pair = (
                entry.departure_icao,
                entry.arrival_icao,
            )

            by_pair.setdefault(
                pair,
                [],
            ).append(entry)

        results: list[OperationsAssessment] = []

        # ----------------------------------------------------
        # Evaluate Individual Routes
        # ----------------------------------------------------

        for route in routes:
            pair = (
                route["departure_icao"],
                route["arrival_icao"],
            )

            choices = by_pair.get(pair, [])

            # Match the specific selected aircraft.
            with_aircraft = [
                entry
                for entry in choices
                if any(
                    aircraft.id == route["aircraft_id"]
                    for aircraft in entry.aircraft
                )
            ]

            # Identify entries recorded as real-world routes.
            confirmed = [
                entry
                for entry in with_aircraft
                if entry.is_real_world_route
            ]

            # ------------------------------------------------
            # Recorded Real-World Assignment
            # ------------------------------------------------

            if confirmed:
                match = confirmed[0]

                results.append(
                    OperationsAssessment(
                        score=100.0,
                        verified_catalog_match=True,
                        airline=(
                            match.airline.name
                            if match.airline
                            else None
                        ),
                        flight_number=match.flight_number,
                        notes=(
                            "Matches an aircraft assignment recorded "
                            "as a real-world service in local catalog; "
                            "current operation unverified",
                        ),
                    )
                )

            # ------------------------------------------------
            # Recorded Aircraft / Route Pair
            # ------------------------------------------------

            elif with_aircraft:
                results.append(
                    OperationsAssessment(
                        score=65.0,
                        verified_catalog_match=False,
                        airline=None,
                        flight_number=None,
                        notes=(
                            "Matching aircraft and airport pair in "
                            "local catalog; not verified real-world service",
                        ),
                    )
                )

            # ------------------------------------------------
            # Recorded Route, Different Aircraft
            # ------------------------------------------------

            elif choices:
                results.append(
                    OperationsAssessment(
                        score=35.0,
                        verified_catalog_match=False,
                        airline=None,
                        flight_number=None,
                        notes=(
                            "Airport pair stored, but selected aircraft "
                            "has no recorded assignment",
                        ),
                    )
                )

            # ------------------------------------------------
            # Unknown Route
            # ------------------------------------------------

            else:
                results.append(
                    OperationsAssessment(
                        score=None,
                        verified_catalog_match=False,
                        airline=None,
                        flight_number=None,
                        notes=(
                            "No route evidence in local catalog; "
                            "realism unknown",
                        ),
                    )
                )

        return results

    # ========================================================
    # Schedule Management
    # ========================================================

    def set_schedules(
        self,
        schedules: list[FlightSchedule],
    ) -> None:
        """
        Replace the current source-backed schedule collection.

        This allows schedules to be loaded after engine
        initialization without recreating the engine.
        """
        self.schedules = list(schedules)

    # ========================================================
    # Schedule Helpers
    # ========================================================

    @staticmethod
    def normalize_code(
        value: str | None,
    ) -> str | None:
        """
        Normalize airline, airport or aircraft identifiers.

        Returns None when no identifier is provided.
        """
        if not value:
            return None

        return value.strip().upper()

    @staticmethod
    def check_operating_date(
        schedule: FlightSchedule,
        departure_date: date | None,
    ) -> bool | None:
        """
        Determine whether a schedule includes a requested date.

        Returns:
            True:
                The schedule includes the date.

            False:
                The schedule excludes the date.

            None:
                There is insufficient information to determine
                whether the flight operates on that date.
        """
        if departure_date is None:
            return None

        if schedule.valid_from is None:
            return None

        if schedule.valid_until is None:
            return None

        if not schedule.operating_days:
            return None

        if not (
            schedule.valid_from
            <= departure_date
            <= schedule.valid_until
        ):
            return False

        return (
            departure_date.isoweekday()
            in schedule.operating_days
        )

    @classmethod
    def match_aircraft(
        cls,
        expected: str | None,
        scheduled: str | None,
    ) -> AircraftMatch:
        """
        Compare a selected aircraft with scheduled equipment.

        Uses exact ICAO aircraft code matching.

        Aircraft family equivalence must come from an
        explicit mapping, not string similarity.
        """
        expected = cls.normalize_code(expected)
        scheduled = cls.normalize_code(scheduled)

        if not expected or not scheduled:
            return AircraftMatch.UNKNOWN

        if expected == scheduled:
            return AircraftMatch.EXACT

        return AircraftMatch.MISMATCH

    # ========================================================
    # Airline Schedule Lookup
    # ========================================================

    def lookup_schedule(
        self,
        request: ScheduleLookupRequest,
    ) -> ScheduleLookupResponse:
        """
        Find airline schedules matching the requested route.

        Filters by:
        - Departure airport
        - Arrival airport
        - Airline ICAO, when provided
        - Requested operating date, when verifiable

        Also evaluates the selected aircraft against
        scheduled aircraft equipment.

        Returns:
            ScheduleLookupResponse with matching schedules,
            verification status and warnings.

        A verified schedule still depends on the quality,
        freshness and provenance of its source.
        """
        departure = self.normalize_code(
            request.departure_icao
        )

        arrival = self.normalize_code(
            request.arrival_icao
        )

        airline = self.normalize_code(
            request.airline_icao
        )

        logger.info(
            "SCHEDULE LOOKUP | %s -> %s | "
            "airline=%s | date=%s | aircraft=%s",
            departure,
            arrival,
            airline,
            request.departure_date,
            request.aircraft_icao,
        )

        matches: list[ScheduleMatch] = []

        # ----------------------------------------------------
        # Evaluate Schedule Records
        # ----------------------------------------------------

        for schedule in self.schedules:
            if (
                self.normalize_code(
                    schedule.departure_icao
                )
                != departure
            ):
                continue

            if (
                self.normalize_code(
                    schedule.arrival_icao
                )
                != arrival
            ):
                continue

            if airline and (
                self.normalize_code(
                    schedule.airline_icao
                )
                != airline
            ):
                continue

            # ------------------------------------------------
            # Operating Date
            # ------------------------------------------------

            operates = self.check_operating_date(
                schedule,
                request.departure_date,
            )

            if operates is False:
                continue

            # ------------------------------------------------
            # Aircraft Matching
            # ------------------------------------------------

            aircraft_match = self.match_aircraft(
                request.aircraft_icao,
                schedule.aircraft_icao,
            )

            reasons: list[str] = []

            if operates is True:
                reasons.append(
                    "Schedule includes the requested date."
                )

            elif request.departure_date is not None:
                reasons.append(
                    "Operating date cannot be confirmed."
                )

            if aircraft_match == AircraftMatch.EXACT:
                reasons.append(
                    "Scheduled aircraft ICAO code matches."
                )

            elif aircraft_match == AircraftMatch.MISMATCH:
                reasons.append(
                    "Scheduled aircraft differs from selected aircraft."
                )

            matches.append(
                ScheduleMatch(
                    schedule=schedule,
                    aircraft_match=aircraft_match,
                    operates_on_date=operates,
                    reasons=reasons,
                )
            )

        # ----------------------------------------------------
        # Schedule Verification
        # ----------------------------------------------------

        verified = any(
            match.schedule.status == ScheduleStatus.VERIFIED
            and match.operates_on_date is True
            for match in matches
        )

        if verified:
            schedule_status = ScheduleStatus.VERIFIED

        elif matches:
            schedule_status = ScheduleStatus.UNVERIFIED

        else:
            schedule_status = ScheduleStatus.UNKNOWN

        logger.info(
            "SCHEDULE RESULT | %s -> %s | "
            "status=%s | matches=%d",
            departure,
            arrival,
            schedule_status.value,
            len(matches),
        )

        warnings: list[str] = []

        if not matches:
            warnings.append(
                "No matching schedule evidence is available."
            )

        # ----------------------------------------------------
        # Response
        # ----------------------------------------------------

        return ScheduleLookupResponse(
            departure_icao=departure or "",
            arrival_icao=arrival or "",
            departure_date=request.departure_date,
            status=schedule_status,
            matches=matches,
            warnings=warnings,
        )
