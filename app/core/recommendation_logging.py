from __future__ import annotations

import logging
import time

from typing import Any
from app.core.logging import get_logger


logger = get_logger("recommendations")


class RecommendationLogger:
    def __init__(self, request_id: str):
        self.request_id = request_id
        self.started = time.perf_counter()
        self.checked = 0
        self.accepted = 0
        self.rejected = 0

    def _log(
        self,
        level: int,
        stage: str,
        message: str,
        **values: Any,
    ) -> None:
        details = " · ".join(
            f"{key}={value}"
            for key, value in values.items()
            if value is not None
        )

        suffix = f" · {details}" if details else ""

        logger.log(
            level,
            "[%s] %-12s | %s%s",
            self.request_id,
            stage,
            message,
            suffix,
        )

    def start(
        self,
        departure: str,
        category: str | None,
        airport_mode: str,
    ) -> None:
        self._log(
            logging.INFO,
            "START",
            "Recommendation generation started",
            departure=departure,
            category=category or "any",
            airport_mode=airport_mode,
        )

    def candidates_loaded(self, count: int) -> None:
        self._log(
            logging.INFO,
            "CATALOG",
            "Candidate airports loaded",
            count=count,
        )

    def airport(
        self,
        icao: str,
        name: str,
        index: int,
        total: int,
        distance_nm: float | None = None,
    ) -> None:
        self.checked += 1

        self._log(
            logging.INFO,
            "AIRPORT",
            f"[{index}/{total}] {icao} - {name}",
            distance_nm=(
                round(distance_nm, 1)
                if distance_nm is not None
                else None
            ),
        )

    def reject(
        self,
        icao: str,
        reason: str,
    ) -> None:
        self.rejected += 1

        self._log(
            logging.INFO,
            "REJECT",
            icao,
            reason=reason,
        )

    def accept(
        self,
        icao: str,
        aircraft: str,
        duration_hours: float | None,
        flyability: float | None,
        final_score: float | None,
    ) -> None:
        self.accepted += 1

        self._log(
            logging.INFO,
            "ACCEPT",
            icao,
            aircraft=aircraft,
            duration_h=duration_hours,
            flyability=flyability,
            final_score=final_score,
        )

    def score(
        self,
        icao: str,
        aircraft: str,
        scores: dict[str, Any],
    ) -> None:
        self._log(
            logging.DEBUG,
            "SCORING",
            f"{icao} / {aircraft}",
            **scores,
        )

    def response(
        self,
        generated: int,
        evaluated: int,
        eligible: int,
        returned: int,
    ) -> None:
        elapsed = time.perf_counter() - self.started

        self._log(
            logging.INFO,
            "RESPONSE",
            "Recommendation response prepared",
            generated=generated,
            evaluated=evaluated,
            eligible=eligible,
            returned=returned,
            elapsed_s=round(elapsed, 3),
        )

    def failure(self, exception: Exception) -> None:
        self._log(
            logging.ERROR,
            "FAILED",
            str(exception),
            elapsed_s=round(
                time.perf_counter() - self.started,
                3,
            ),
        )
