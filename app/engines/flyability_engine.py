from __future__ import annotations

from dataclasses import dataclass, field

from app.db.models.aircraft import Aircraft
from app.providers.airport_catalog import AirportRecord


@dataclass(frozen=True)
class FlyabilityResult:
    score: float
    status: str
    breakdown: dict[str, float]
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    evidence_coverage: dict[str, bool] = field(
        default_factory=dict
    )
    personal_feedback_available: bool = False


class FlyabilityEngine:
    """
    Estimates how appealing a flight would be to experience
    or fly again in Microsoft Flight Simulator.

    This is NOT an aircraft safety or airport compatibility
    engine. Rejections must be handled separately by the
    existing aircraft/airport validation engines.

    Score distribution:
        Scenery:                 25
        Approach experience:     20
        Airport experience:      20
        Route variety:           15
        Aircraft enjoyment:      10
        Personal replayability:  10

    Total: 100

    Unknown enjoyment factors receive neutral baseline
    values and are explicitly identified as unverified.
    """

    MAX_SCORE = 100.0

    @staticmethod
    def _clamp(
        value: float,
        minimum: float,
        maximum: float,
    ) -> float:
        return max(minimum, min(value, maximum))

    @staticmethod
    def _scenery_score(
        departure: AirportRecord,
        arrival: AirportRecord,
    ) -> tuple[float, list[str]]:

        score = 12.5
        reasons = []

        if departure.has_addon_scenery:
            score += 6.25
            reasons.append(
                "Installed departure airport scenery."
            )

        if arrival.has_addon_scenery:
            score += 6.25
            reasons.append(
                "Installed arrival airport scenery."
            )

        return round(score, 2), reasons

    @staticmethod
    def _approach_score(
        departure: AirportRecord,
        arrival: AirportRecord,
    ) -> float:
        return 10.0

    @staticmethod
    def _airport_experience_score(
        departure: AirportRecord,
        arrival: AirportRecord,
    ) -> tuple[float, list[str]]:

        score = 10.0
        reasons = []

        if departure.has_addon_scenery:
            score += 5.0
            reasons.append(
                "Departure airport has installed scenery."
            )

        if arrival.has_addon_scenery:
            score += 5.0
            reasons.append(
                "Arrival airport has installed scenery."
            )

        return round(score, 2), reasons

    @staticmethod
    def _route_variety_score() -> float:
        return 7.5

    @staticmethod
    def _aircraft_enjoyment_score(
        aircraft: Aircraft,
    ) -> tuple[float, list[str]]:

        score = 5.0
        reasons = []

        if aircraft.is_owned:
            score += 5.0
            reasons.append(
                "Aircraft is available in your MSFS fleet."
            )

        return score, reasons

    @staticmethod
    def _personal_replayability_score() -> float:
        return 5.0

    def evaluate(
        self,
        *,
        departure: AirportRecord,
        arrival: AirportRecord,
        aircraft: Aircraft,
        duration_min: int,
    ) -> FlyabilityResult:

        reasons: list[str] = []
        warnings: list[str] = []

        scenery, scenery_reasons = self._scenery_score(
            departure,
            arrival,
        )

        airport_experience, airport_reasons = (
            self._airport_experience_score(
                departure,
                arrival,
            )
        )

        aircraft_enjoyment, aircraft_reasons = (
            self._aircraft_enjoyment_score(aircraft)
        )

        breakdown = {
            "scenery": scenery,
            "approach_experience": self._approach_score(
                departure,
                arrival,
            ),
            "airport_experience": airport_experience,
            "route_variety": self._route_variety_score(),
            "aircraft_enjoyment": aircraft_enjoyment,
            "personal_replayability": (
                self._personal_replayability_score()
            ),
        }

        score = self._clamp(
            sum(breakdown.values()),
            0.0,
            self.MAX_SCORE,
        )

        reasons.extend(scenery_reasons)
        reasons.extend(airport_reasons)
        reasons.extend(aircraft_reasons)

        evidence_coverage = {
            "scenery": (
                departure.has_addon_scenery
                or arrival.has_addon_scenery
            ),
            "approach_experience": False,
            "airport_experience": (
                departure.has_addon_scenery
                or arrival.has_addon_scenery
            ),
            "route_variety": False,
            "aircraft_enjoyment": False,
            "personal_replayability": False,
        }

        warnings.append(
            "Replayability is estimated. Terrain, approach "
            "experience, and personal feedback are not yet "
            "available."
        )

        return FlyabilityResult(
            score=round(score, 2),
            status="estimated",
            breakdown=breakdown,
            reasons=list(dict.fromkeys(reasons)),
            warnings=warnings,
            evidence_coverage=evidence_coverage,
            personal_feedback_available=False,
        )