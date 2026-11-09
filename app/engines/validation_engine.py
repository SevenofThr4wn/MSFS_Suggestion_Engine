from dataclasses import dataclass, asdict
from typing import Any

from app.core.consts.runway import PAVED, UNPAVED

@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: str
    airport_icao: str | None
    message: str
    observed: float | str | None = None
    required: float | str | None = None
    unit: str | None = None

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class ValidationOutcome:
    status: str
    issues: tuple[ValidationIssue, ...]
    departure_runway: str | None
    arrival_runway: str | None

    def to_dict(self):
        return {
            "status": self.status,
            "issues": [
                issue.to_dict()
                for issue in self.issues
            ],
            "departure_runway": self.departure_runway,
            "arrival_runway": self.arrival_runway,
        }


class ValidationEngine:
    def evaluate(
        self,
        aircraft: Any,
        departure: Any,
        arrival: Any,
        distance_nm: float,
        *,
        require_paved: bool = True,
    ) -> ValidationOutcome:
        issues = []

        # --------------------------------------------------
        # Route Distance Validation
        # --------------------------------------------------

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
                        and surface not in PAVED
                        and surface not in UNPAVED
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
                    and surface in UNPAVED
                ):
                    continue

                if (
                    length is None
                    or width is None
                    or (
                        require_paved
                        and surface not in PAVED
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
                        in UNPAVED
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
