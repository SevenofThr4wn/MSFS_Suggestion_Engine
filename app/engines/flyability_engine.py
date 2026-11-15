from __future__ import annotations

from app.core.classes.validation import FlyabilityResult
from app.db.models.aircraft import Aircraft
from app.providers.airport_catalog import AirportRecord


class FlyabilityEngine:

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