from __future__ import annotations

import csv

from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Literal

from app.core.enums import SuitabilityStatus
from app.db.models.aircraft import Aircraft
from app.engines.aircraft_engine import AircraftEngine
from app.providers.airport_catalog import AirportRecord
from app.providers.runway_provider import RunwayData
from app.schemas.aircraft import AircraftCheck, CheckStatus
from app.schemas.route import AirportMode

from app.core.consts.airports import AIRPORT_SIZE_RANK, MAIN_HUB_CODES
from app.core.consts.runway import PAVED_SURFACE_CODES, UNPAVED_SURFACE_CODES


Suitability = Literal[
    "preliminary_pass",
    "rejected",
    "indeterminate",
]


@dataclass(frozen=True)
class GateSuggestion:
    """A candidate gate selected from local airport inventory."""

    airport_icao: str
    gate: str | None
    status: str
    source: str
    reasons: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)

@dataclass(frozen=True)
class SuitabilityProfile:
    minimum_airport_size: str | None
    minimum_runway_length_m: float
    minimum_runway_width_m: float
    require_paved_runway: bool = True


DEFAULT_PROFILES = {
    "wide_body": SuitabilityProfile(
        minimum_airport_size="medium_airport",
        minimum_runway_length_m=2500,
        minimum_runway_width_m=40,
    ),
    "narrow_body": SuitabilityProfile(
        minimum_airport_size="medium_airport",
        minimum_runway_length_m=1500,
        minimum_runway_width_m=30,
    ),
    "regional_jet": SuitabilityProfile(
        minimum_airport_size="small_airport",
        minimum_runway_length_m=1200,
        minimum_runway_width_m=25,
    ),
    "turboprop": SuitabilityProfile(
        minimum_airport_size="small_airport",
        minimum_runway_length_m=800,
        minimum_runway_width_m=18,
        require_paved_runway=False,
    ),
}


@dataclass(frozen=True)
class AirportSuitabilityResult:
    airport_icao: str
    aircraft_id: int
    operation: str
    status: SuitabilityStatus
    selected_runway: RunwayData | None
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class RunwayAssessment:
    runway: RunwayData
    check: AircraftCheck


@dataclass(frozen=True)
class AirportAssessment:
    airport: AirportRecord
    operation: str
    suitability: Suitability
    selected_runway: RunwayAssessment | None
    assessments: list[RunwayAssessment]
    warnings: list[str]

@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: str
    airport_icao: str | None
    message: str
    observed: float | str | None = None
    required: float | str | None = None
    unit: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ValidationOutcome:
    status: str
    issues: tuple[ValidationIssue, ...]
    departure_runway: str | None
    arrival_runway: str | None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "issues": [
                issue.to_dict()
                for issue in self.issues
            ],
            "departure_runway": self.departure_runway,
            "arrival_runway": self.arrival_runway,
        }

class AirportEngine:
    """
    Airport discovery, runway assessment, and aircraft
    compatibility screening.

    Supports:
    - Airport discovery filtering
    - Aircraft category suitability profiles
    - Airport size restrictions
    - Scheduled service requirements
    - Runway length and width screening
    - Runway surface screening
    - Preliminary aircraft runway compatibility

    Results are simulator-planning estimates and are not
    certified aircraft performance or dispatch calculations.
    """

    def __init__(self, gate_inventory_path: str | Path | None = None) -> None:
        self._gates: dict[str, list[dict[str, str]]] = {}

        if gate_inventory_path is not None:
            self.load_gate_inventory(gate_inventory_path)


    @staticmethod
    def is_eligible(
        airport: AirportRecord,
        mode: AirportMode,
    ) -> bool:
        """Determine whether an airport meets discovery criteria."""
        if airport.is_closed is True:
            return False

        if mode == AirportMode.ALL:
            return True

        if mode == AirportMode.MAIN_HUBS:
            return airport.icao_code in MAIN_HUB_CODES

        if mode == AirportMode.MAJOR:
            return (
                airport.airport_type == "large_airport"
                and airport.scheduled_service is True
            )

        if mode == AirportMode.COMMERCIAL:
            return (
                airport.airport_type in {
                    "large_airport",
                    "medium_airport",
                }
                and airport.scheduled_service is True
            )

        return False


    @staticmethod
    def _is_paved(
        surface: str | None,
    ) -> bool | None:
        """Classify runway surfaces conservatively."""
        if not surface:
            return None

        normalized = surface.strip().upper()

        if normalized in PAVED_SURFACE_CODES:
            return True

        if normalized in UNPAVED_SURFACE_CODES:
            return False

        return None


    @staticmethod
    def _profile_for(
        aircraft: Aircraft,
    ) -> SuitabilityProfile:
        """Return configured suitability requirements."""
        return DEFAULT_PROFILES.get(
            aircraft.category,
            SuitabilityProfile(
                minimum_airport_size=None,
                minimum_runway_length_m=0,
                minimum_runway_width_m=0,
                require_paved_runway=False,
            ),
        )


    @staticmethod
    def assess_runway(
        runway: RunwayData,
        aircraft: Aircraft,
        operation: str,
    ) -> RunwayAssessment:
        """Evaluate runway length against aircraft reference data."""
        if operation not in {"takeoff", "landing"}:
            raise ValueError("Invalid operation.")

        reference_distance = (
            aircraft.takeoff_distance_m
            if operation == "takeoff"
            else aircraft.landing_distance_m
        )

        check = AircraftEngine.evaluate_runway(
            reference_distance,
            runway.length_m,
            operation,
        )

        return RunwayAssessment(
            runway=runway,
            check=check,
        )


    def evaluate_runways(
        self,
        airport: AirportRecord,
        aircraft: Aircraft,
        operation: str,
    ) -> AirportAssessment:
        if operation not in {"takeoff", "landing"}:
            raise ValueError("Invalid operation.")

        assessments = [
            self.assess_runway(
                runway,
                aircraft,
                operation,
            )
            for runway in airport.runways
            if not runway.closed
        ]

        priority = {
            CheckStatus.PASS: 0,
            CheckStatus.UNKNOWN: 1,
            CheckStatus.FAIL: 2,
            CheckStatus.SKIPPED: 3,
        }

        assessments.sort(
            key=lambda item: (
                priority[item.check.status],
                -(
                    item.runway.length_m
                    if item.runway.length_m is not None
                    else 0
                ),
            )
        )

        selected = (
            assessments[0]
            if assessments
            else None
        )

        statuses = {
            assessment.check.status
            for assessment in assessments
        }

        if CheckStatus.PASS in statuses:
            suitability = "preliminary_pass"

        elif (
            CheckStatus.UNKNOWN in statuses
            or not assessments
        ):
            suitability = "indeterminate"

        else:
            suitability = "rejected"

        warnings = [
            "Physical runway length screening only; "
            "declared distances and aircraft performance "
            "are not verified."
        ]

        if not assessments:
            warnings.append(
                "No open runway records are available."
            )

        if airport.elevation_ft is None:
            warnings.append(
                "Airport elevation is unavailable."
            )

        return AirportAssessment(
            airport=airport,
            operation=operation,
            suitability=suitability,
            selected_runway=selected,
            assessments=assessments,
            warnings=warnings,
        )

    def load_gate_inventory(
        self,
        csv_path: str | Path,
    ) -> None:
        """
        Load gate inventory from a CSV file.

        The inventory can specify:
        - airport_icao
        - gate
        - aircraft_icao
        - international

        Existing inventory is replaced when a new CSV is loaded.
        """
        path = Path(csv_path)

        if not path.is_file():
            raise FileNotFoundError(
                f"Gate inventory not found: {path}"
            )

        gates: dict[str, list[dict[str, str]]] = {}

        with path.open(
            newline="",
            encoding="utf-8-sig",
        ) as file:
            reader = csv.DictReader(file)

            for row in reader:
                airport_icao = (
                    row.get("airport_icao") or ""
                ).strip().upper()

                gate = (
                    row.get("gate") or ""
                ).strip()

                if not airport_icao or not gate:
                    continue

                gates.setdefault(
                    airport_icao,
                    [],
                ).append({
                    **row,
                    "airport_icao": airport_icao,
                    "gate": gate,
                })

        self._gates = gates

    
    def suggest_gate(
        self,
        airport_icao: str,
        aircraft: Aircraft,
        *,
        international: bool | None = None,
    ) -> GateSuggestion:
        """
        Suggest a compatible airport gate from local inventory.

        Compatibility checks:
        - Airport ICAO
        - Aircraft ICAO, when restricted
        - International/domestic restrictions, when specified

        Never generates or invents a gate identifier.

        Returns:
            GateSuggestion containing either an inventory
            candidate or an unknown result.
        """
        code = airport_icao.strip().upper()

        matches: list[dict[str, str]] = []

        aircraft_icao = (
            getattr(aircraft, "icao_code", None) or ""
        ).strip().upper()

        for row in self._gates.get(code, []):
    
            supported_aircraft = [
                value.strip().upper()
                for value in (
                    row.get("aircraft_icao") or ""
                ).split(";")
                if value.strip()
            ]

            if (
                supported_aircraft
                and aircraft_icao not in supported_aircraft
            ):
                continue

            restriction = (
                row.get("international") or ""
            ).strip().lower()

            if (
                international is not None
                and restriction in {"yes", "no"}
            ):
                supports_international = (
                    restriction == "yes"
                )

                if supports_international != international:
                    continue

            matches.append(row)

        if not matches:
            return GateSuggestion(
                airport_icao=code,
                gate=None,
                status="unknown",
                source="no_verified_inventory",
                reasons=(
                    "No compatible gate in provided inventory; "
                    "ask ATC/GSX or choose manually",
                ),
            )

        selected = min(
            matches,
            key=lambda row: row["gate"],
        )

        return GateSuggestion(
            airport_icao=code,
            gate=selected["gate"],
            status="candidate",
            source="local_gate_inventory",
            reasons=(
                "Candidate from user-maintained stand list, "
                "not a confirmed ATC assignment",
            ),
        )


    def evaluate(
        self,
        airport: AirportRecord,
        aircraft: Aircraft,
        operation: str,
        *,
        minimum_airport_size: str | None = None,
        require_paved_runway: bool | None = None,
        require_known_runway_data: bool = False,
        require_scheduled_service: bool = False,
    ) -> AirportSuitabilityResult:
        """
        Screen an airport for a particular aircraft operation.

        Uses aircraft category, physical runway dimensions,
        runway surface and selected airport metadata.

        Preserves the original AirportSuitabilityEngine
        evaluation behaviour.
        """
        if operation not in {"takeoff", "landing"}:
            raise ValueError("Invalid operation.")

        profile = self._profile_for(aircraft)

        reasons: list[str] = []
        warnings: list[str] = []


        if airport.is_closed is True:
            return AirportSuitabilityResult(
                airport_icao=airport.icao_code,
                aircraft_id=aircraft.id,
                operation=operation,
                status=SuitabilityStatus.FAIL,
                selected_runway=None,
                reasons=("Airport is recorded as closed.",),
                warnings=(),
            )

        if airport.is_closed is None:
            warnings.append(
                "Airport closure status is unknown."
            )


        required_size = (
            minimum_airport_size
            if minimum_airport_size is not None
            else profile.minimum_airport_size
        )

        if required_size:
            required_rank = AIRPORT_SIZE_RANK[required_size]

            actual_rank = AIRPORT_SIZE_RANK.get(
                airport.airport_type
            )

            if actual_rank is not None:
                if actual_rank < required_rank:
                    return AirportSuitabilityResult(
                        airport_icao=airport.icao_code,
                        aircraft_id=aircraft.id,
                        operation=operation,
                        status=SuitabilityStatus.FAIL,
                        selected_runway=None,
                        reasons=(
                            "Airport is below the minimum size.",
                        ),
                        warnings=(),
                    )

            elif airport.airport_type is not None:
                return AirportSuitabilityResult(
                    airport_icao=airport.icao_code,
                    aircraft_id=aircraft.id,
                    operation=operation,
                    status=SuitabilityStatus.FAIL,
                    selected_runway=None,
                    reasons=(
                        "Airport type is not eligible.",
                    ),
                    warnings=(),
                )

            else:
                warnings.append(
                    "Airport size is unknown."
                )


        if require_scheduled_service:
            if airport.scheduled_service is False:
                return AirportSuitabilityResult(
                    airport_icao=airport.icao_code,
                    aircraft_id=aircraft.id,
                    operation=operation,
                    status=SuitabilityStatus.FAIL,
                    selected_runway=None,
                    reasons=(
                        "No scheduled service recorded.",
                    ),
                    warnings=(),
                )

            if airport.scheduled_service is None:
                warnings.append(
                    "Scheduled service status is unknown."
                )


        paved_required = (
            profile.require_paved_runway
            if require_paved_runway is None
            else require_paved_runway
        )

        reference_length = (
            aircraft.takeoff_distance_m
            if operation == "takeoff"
            else aircraft.landing_distance_m
        )

        required_length = (
            profile.minimum_runway_length_m
        )

        if (
            reference_length is not None
            and reference_length > 0
        ):
            required_length = max(
                required_length,
                reference_length,
            )

        else:
            warnings.append(
                "Aircraft reference distance is unavailable."
            )

        possible: list[RunwayData] = []
        uncertain: list[RunwayData] = []


        for runway in airport.runways:
            if runway.closed:
                continue

            if (
                runway.length_m is not None
                and runway.length_m < required_length
            ):
                continue

            if (
                runway.width_m is not None
                and runway.width_m
                < profile.minimum_runway_width_m
            ):
                continue

            surface_status = self._is_paved(
                runway.surface
            )

            if (
                paved_required
                and surface_status is False
            ):
                continue

            unknown = (
                runway.length_m is None
                or runway.width_m is None
                or (
                    paved_required
                    and surface_status is None
                )
            )

            if unknown:
                uncertain.append(runway)
            else:
                possible.append(runway)


        def longest(
            runways: list[RunwayData],
        ) -> RunwayData:
            return max(
                runways,
                key=lambda runway: (
                    runway.length_m or 0
                ),
            )

        if possible:
            selected = longest(possible)

            reasons.append(
                "Runway meets preliminary dimensions "
                "and surface requirements."
            )

            status = SuitabilityStatus.PASS

        elif (
            uncertain
            and not require_known_runway_data
        ):
            selected = longest(uncertain)

            warnings.append(
                "Runway data is incomplete."
            )

            status = SuitabilityStatus.UNKNOWN

        else:
            selected = None

            status = SuitabilityStatus.FAIL

            reasons.append(
                "No runway satisfies the configured "
                "screening requirements."
            )


        if (
            status == SuitabilityStatus.PASS
            and warnings
        ):
            status = SuitabilityStatus.UNKNOWN

        return AirportSuitabilityResult(
            airport_icao=airport.icao_code,
            aircraft_id=aircraft.id,
            operation=operation,
            status=status,
            selected_runway=selected,
            reasons=tuple(reasons),
            warnings=tuple(warnings),
        )

    def validate_route(
        self,
        aircraft: Aircraft,
        departure: AirportRecord,
        arrival: AirportRecord,
        distance_nm: float,
        *,
        require_paved: bool = True,
    ) -> ValidationOutcome:
        """
        Validate an aircraft and airport pair for a flight.

        Preserves structured validation issues and runway
        selections for recommendation analysis.

        This is preliminary simulator screening, not
        real-world operational certification.
        """
        issues: list[ValidationIssue] = []



        if distance_nm <= 0:
            issues.append(
                ValidationIssue(
                    code="INVALID_ROUTE_DISTANCE",
                    severity="reject",
                    airport_icao=None,
                    message="Route distance must be positive",
                    observed=distance_nm,
                )
            )

        # --------------------------------------------------
        # Aircraft Range Validation
        # --------------------------------------------------

        nominal_range = getattr(
            aircraft,
            "range_nm",
            None,
        )

        if nominal_range is None or nominal_range <= 0:
            issues.append(
                ValidationIssue(
                    code="RANGE_UNKNOWN",
                    severity="unknown",
                    airport_icao=None,
                    message="Aircraft reference range is unavailable",
                )
            )

        elif distance_nm * 1.10 > nominal_range:
            issues.append(
                ValidationIssue(
                    code="AIRCRAFT_RANGE_EXCEEDED",
                    severity="reject",
                    airport_icao=None,
                    message=(
                        "Estimated mission distance exceeds "
                        "stored aircraft reference range"
                    ),
                    observed=round(distance_nm * 1.10, 1),
                    required=nominal_range,
                    unit="NM",
                )
            )

        # --------------------------------------------------
        # Airport and Runway Validation
        # --------------------------------------------------

        selected = []

        for airport, operation in (
            (departure, "departure"),
            (arrival, "arrival"),
        ):
            code = airport.icao_code

            # Airport closure status
            if getattr(airport, "is_closed", None) is True:
                issues.append(
                    ValidationIssue(
                        code="AIRPORT_CLOSED",
                        severity="reject",
                        airport_icao=code,
                        message="Airport is marked closed",
                    )
                )

            elif getattr(airport, "is_closed", None) is None:
                issues.append(
                    ValidationIssue(
                        code="AIRPORT_CLOSURE_UNKNOWN",
                        severity="unknown",
                        airport_icao=code,
                        message="Airport closure status unavailable",
                    )
                )

            # Aircraft reference performance
            reference = getattr(
                aircraft,
                (
                    "takeoff_distance_m"
                    if operation == "departure"
                    else "landing_distance_m"
                ),
                None,
            )

            if reference is None or reference <= 0:
                issues.append(
                    ValidationIssue(
                        code="AIRCRAFT_PERFORMANCE_UNKNOWN",
                        severity="unknown",
                        airport_icao=code,
                        message=(
                            f"{operation.title()} reference "
                            "distance unavailable"
                        ),
                    )
                )

            # Aircraft category runway requirements
            profile_min = (
                2500
                if getattr(aircraft, "category", None) == "wide_body"
                else (
                    1500
                    if getattr(aircraft, "category", None) == "narrow_body"
                    else 0
                )
            )

            required_length = max(
                profile_min,
                reference or 0,
            )

            width_min = (
                40
                if getattr(aircraft, "category", None) == "wide_body"
                else (
                    30
                    if getattr(aircraft, "category", None) == "narrow_body"
                    else 0
                )
            )

            # --------------------------------------------------
            # Find Compatible Runways
            # --------------------------------------------------

            candidates = []
            uncertain = False

            longest = 0.0
            widest = 0.0

            for runway in getattr(airport, "runways", ()):
                if runway.closed:
                    continue

                length = runway.length_m
                width = runway.width_m

                longest = max(
                    longest,
                    length or 0,
                )

                widest = max(
                    widest,
                    width or 0,
                )

                surface = (
                    runway.surface or ""
                ).strip().upper()

                if (
                    length is None
                    or width is None
                    or (
                        require_paved
                        and surface not in PAVED_SURFACE_CODES
                        and surface not in UNPAVED_SURFACE_CODES
                    )
                ):
                    uncertain = True

                if (
                    length is not None
                    and length < required_length
                ):
                    continue

                if (
                    width is not None
                    and width < width_min
                ):
                    continue

                if (
                    require_paved
                    and surface in UNPAVED_SURFACE_CODES
                ):
                    continue

                if (
                    length is None
                    or width is None
                    or (
                        require_paved
                        and surface not in PAVED_SURFACE_CODES
                    )
                ):
                    continue

                candidates.append(runway)

            # --------------------------------------------------
            # Runway Selection
            # --------------------------------------------------

            if candidates:
                chosen = max(
                    candidates,
                    key=lambda runway: runway.length_m or 0,
                )

                selected.append(chosen.designation)

            else:
                selected.append(None)

                all_runways = [
                    runway
                    for runway in getattr(airport, "runways", ())
                    if not runway.closed
                ]

                if not all_runways:
                    issues.append(
                        ValidationIssue(
                            code="RUNWAY_DATA_MISSING",
                            severity="unknown",
                            airport_icao=code,
                            message=(
                                "No open runway records available"
                            ),
                        )
                    )

                elif longest and longest < required_length:
                    issues.append(
                        ValidationIssue(
                            code="RUNWAY_TOO_SHORT",
                            severity="reject",
                            airport_icao=code,
                            message=(
                                f"No open {operation} runway meets "
                                "minimum reference length"
                            ),
                            observed=round(longest, 1),
                            required=round(required_length, 1),
                            unit="m",
                        )
                    )

                elif widest and widest < width_min:
                    issues.append(
                        ValidationIssue(
                            code="RUNWAY_TOO_NARROW",
                            severity="reject",
                            airport_icao=code,
                            message=(
                                f"No open {operation} runway meets "
                                "minimum reference width"
                            ),
                            observed=round(widest, 1),
                            required=width_min,
                            unit="m",
                        )
                    )

                elif (
                    all(
                        (runway.surface or "").strip().upper()
                        in UNPAVED_SURFACE_CODES
                        for runway in all_runways
                    )
                    and require_paved
                ):
                    issues.append(
                        ValidationIssue(
                            code="RUNWAY_SURFACE_UNSUITABLE",
                            severity="reject",
                            airport_icao=code,
                            message=(
                                "Only unpaved runway surfaces found"
                            ),
                        )
                    )

                else:
                    issues.append(
                        ValidationIssue(
                            code=(
                                "RUNWAY_COMPATIBILITY_UNKNOWN"
                                if uncertain
                                else "NO_COMPATIBLE_RUNWAY"
                            ),
                            severity=(
                                "unknown"
                                if uncertain
                                else "reject"
                            ),
                            airport_icao=code,
                            message=(
                                "Cannot identify a qualifying runway"
                            ),
                        )
                    )

        # --------------------------------------------------
        # Final Validation Status
        # --------------------------------------------------

        status = (
            "rejected"
            if any(
                issue.severity == "reject"
                for issue in issues
            )
            else (
                "indeterminate"
                if issues
                else "preliminary_pass"
            )
        )

        return ValidationOutcome(
            status=status,
            issues=tuple(issues),
            departure_runway=selected[0],
            arrival_runway=selected[1],
        )
