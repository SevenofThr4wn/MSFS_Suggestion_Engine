from app.core.logging import get_logger
from app.db.repositories.aircraft_repository import (
    AircraftRepository,
)
from app.db.models.aircraft import Aircraft
from app.schemas.aircraft import (
    AircraftCheck,
    AircraftEvaluationRequest,
    AircraftEvaluationResult,
    AircraftRecommendationResponse,
    CheckStatus,
)


logger = get_logger(__name__)


class AircraftEngine:
    """Evaluate aircraft suitability and rank candidates for a flight route.

    Uses stored aircraft range and runway-reference data for preliminary
    compatibility checks. Recommendations are not operational approvals
    or verified aircraft performance calculations.

    Attributes:
        repository (AircraftRepository): Data source used to retrieve aircraft.
    """

    def __init__(self, repository: AircraftRepository):
        """Initialize the engine with an aircraft data repository.

        Args:
            repository (AircraftRepository): Repository used to list aircraft.
        """
        
        self.repository = repository

    @staticmethod
    def evaluate_range(
        aircraft: Aircraft,
        route_distance_nm: float,
        distance_margin: float,
    ) -> AircraftCheck:
        """
        Evaluates whether an aircraft has sufficient range for a given route.

        Calculates the required flight distance by applying a configurable
        margin to the route distance, then compares the result against the 
        aircraft's stored maximum range.

        Args:
            aircraft (Aircraft): 
                The aircraft being evaluated.
                 
                Must provide a `range_nm` attribute 
                representing its maximum range in nautical miles.
            
            route_distance_nm (float): 
                The planned route distance in nautical miles.

            distance_margin (float):
                Additional distance allowance expressed as a decimal
                fraction. For example, 0.10 represents a 10% margin.

        Returns:
            AircraftCheck: 
                The result of the aircraft range evaluation, containing
                the check status, explanation, required distance, available
                range (when valid), and distance unit
        """    

        required_distance = (
            route_distance_nm * (1 + distance_margin)
        )

        if aircraft.range_nm is None:
            return AircraftCheck(
                status=CheckStatus.UNKNOWN,
                explanation="Aircraft range data is unavailable.",
                required_value=round(required_distance, 2),
                unit="NM",
            )

        if aircraft.range_nm <= 0:
            return AircraftCheck(
                status=CheckStatus.UNKNOWN,
                explanation="Aircraft range data is invalid.",
                required_value=round(required_distance, 2),
                unit="NM",
            )

        if aircraft.range_nm < required_distance:
            return AircraftCheck(
                status=CheckStatus.FAIL,
                explanation=(
                    "Stored aircraft range is below the "
                    "estimated mission distance."
                ),
                required_value=round(required_distance, 2),
                available_value=aircraft.range_nm,
                unit="NM",
            )

        return AircraftCheck(
            status=CheckStatus.PASS,
            explanation=(
                "Stored aircraft range covers the estimated "
                "mission distance. Fuel feasibility is not verified."
            ),
            required_value=round(required_distance, 2),
            available_value=aircraft.range_nm,
            unit="NM",
        )

    @staticmethod
    def evaluate_runway(
        reference_distance_m: float | None,
        available_runway_m: float | None,
        operation: str,
    ) -> AircraftCheck:

        if available_runway_m is None:
            return AircraftCheck(
                status=CheckStatus.UNKNOWN,
                explanation=(
                    f"{operation.capitalize()} runway length "
                    "was not provided."
                ),
                unit="m",
            )

        if (
            reference_distance_m is None
            or reference_distance_m <= 0
        ):
            return AircraftCheck(
                status=CheckStatus.UNKNOWN,
                explanation=(
                    f"Aircraft {operation} reference distance "
                    "is unavailable."
                ),
                available_value=available_runway_m,
                unit="m",
            )

        if available_runway_m < reference_distance_m:
            return AircraftCheck(
                status=CheckStatus.FAIL,
                explanation=(
                    f"Available runway is shorter than the "
                    f"stored {operation} reference distance."
                ),
                required_value=reference_distance_m,
                available_value=available_runway_m,
                unit="m",
            )

        return AircraftCheck(
            status=CheckStatus.PASS,
            explanation=(
                "Runway length meets the stored reference "
                "distance. Operational performance is not verified."
            ),
            required_value=reference_distance_m,
            available_value=available_runway_m,
            unit="m",
        )

    @staticmethod
    def determine_suitability(
        checks: list[AircraftCheck],
    ) -> str:

        statuses = {check.status for check in checks}

        if CheckStatus.FAIL in statuses:
            return "rejected"

        if CheckStatus.UNKNOWN in statuses:
            return "indeterminate"

        return "preliminary_pass"

    @staticmethod
    def calculate_score(
        aircraft: Aircraft,
        request: AircraftEvaluationRequest,
        suitability: str,
    ) -> float:

        # This score represents preferences, not safety.
        score = 0.0

        # Aircraft category: 35 points
        if request.preferred_category:
            if aircraft.category == request.preferred_category:
                score += 35
        else:
            score += 35

        # ICAO aircraft type: 30 points
        if request.preferred_icao_code:
            if aircraft.icao_code == request.preferred_icao_code:
                score += 30
        else:
            score += 30

        # Owned aircraft: 20 points
        if aircraft.is_owned:
            score += 20

        # Completeness of reference data: 15 points
        available_fields = [
            aircraft.range_nm,
            aircraft.takeoff_distance_m,
            aircraft.landing_distance_m,
        ]

        completeness = sum(
            value is not None and value > 0
            for value in available_fields
        ) / len(available_fields)

        score += 15 * completeness

        # Rejected candidates have no ranking eligibility.
        if suitability == "rejected":
            return 0.0

        return round(min(score, 100.0), 2)

    def evaluate_aircraft(
        self,
        aircraft: Aircraft,
        request: AircraftEvaluationRequest,
    ) -> AircraftEvaluationResult:

        range_check = self.evaluate_range(
            aircraft,
            request.route_distance_nm,
            request.distance_margin,
        )

        takeoff_check = self.evaluate_runway(
            aircraft.takeoff_distance_m,
            request.departure_runway_m,
            "takeoff",
        )

        landing_check = self.evaluate_runway(
            aircraft.landing_distance_m,
            request.arrival_runway_m,
            "landing",
        )

        checks = [
            range_check,
            takeoff_check,
            landing_check,
        ]

        suitability = self.determine_suitability(checks)

        reasons = []
        warnings = []

        if request.preferred_category:
            if aircraft.category == request.preferred_category:
                reasons.append("Matches preferred aircraft category")

        if request.preferred_icao_code:
            if aircraft.icao_code == request.preferred_icao_code:
                reasons.append("Matches preferred ICAO aircraft type")

        if aircraft.is_owned:
            reasons.append("Aircraft is in the owned fleet")

        for check in checks:
            if check.status == CheckStatus.PASS:
                reasons.append(check.explanation)
            else:
                warnings.append(check.explanation)

        score = self.calculate_score(
            aircraft,
            request,
            suitability,
        )

        logger.debug(
            "Aircraft %s: suitability=%s, score=%.2f",
            aircraft.display_name,
            suitability,
            score,
        )

        return AircraftEvaluationResult(
            aircraft_id=aircraft.id,
            aircraft_name=aircraft.display_name,
            icao_code=aircraft.icao_code,
            category=aircraft.category,
            is_owned=aircraft.is_owned,
            range_check=range_check,
            takeoff_check=takeoff_check,
            landing_check=landing_check,
            suitability=suitability,
            score=score,
            reasons=reasons,
            warnings=warnings,
        )

    def recommend(
        self,
        request: AircraftEvaluationRequest,
    ) -> AircraftRecommendationResponse:

        aircraft_list = self.repository.list_aircraft(
            owned_only=request.owned_only,
        )

        results = [
            self.evaluate_aircraft(aircraft, request)
            for aircraft in aircraft_list
        ]

        total_evaluated = len(results)

        if request.suitable_only:
            results = [
                result for result in results
                if result.suitability == "preliminary_pass"
            ]

        # Prefer eligible, then unknown, then rejected.
        suitability_priority = {
            "preliminary_pass": 0,
            "indeterminate": 1,
            "rejected": 2,
        }

        results.sort(
            key=lambda result: (
                suitability_priority[result.suitability],
                -result.score,
                result.aircraft_id,
            )
        )

        results = results[:request.limit]

        return AircraftRecommendationResponse(
            total_evaluated=total_evaluated,
            total_returned=len(results),
            recommendations=results,
        )
