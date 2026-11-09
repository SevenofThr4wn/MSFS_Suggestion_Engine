
from __future__ import annotations

import csv
from datetime import date, datetime, time
from pathlib import Path

from pydantic import ValidationError

from app.core.logging import get_logger
from app.schemas.schedule import FlightSchedule


logger = get_logger("schedules.local_provider")


class LocalScheduleProvider:
    """Read source-attributed flight schedules from CSV."""

    def __init__(self, csv_path: str | Path) -> None:
        self.csv_path = Path(csv_path)

    @staticmethod
    def parse_date(value: str | None) -> date | None:
        return date.fromisoformat(value) if value else None

    @staticmethod
    def parse_time(value: str | None) -> time | None:
        return time.fromisoformat(value) if value else None

    @staticmethod
    def parse_datetime(
        value: str | None,
    ) -> datetime | None:
        return datetime.fromisoformat(value) if value else None

    @staticmethod
    def parse_days(value: str | None) -> list[int]:
        if not value:
            return []

        days = [
            int(part.strip())
            for part in value.split(",")
            if part.strip()
        ]

        if any(day < 1 or day > 7 for day in days):
            raise ValueError(
                "Operating days must be integers from 1 to 7."
            )

        return sorted(set(days))

    def load(self) -> list[FlightSchedule]:
        """Validate and load schedule records from a CSV file."""
        if not self.csv_path.is_file():
            logger.warning(
                "SCHEDULE FILE MISSING | path=%s",
                self.csv_path,
            )
            return []

        schedules: list[FlightSchedule] = []

        with self.csv_path.open(
            "r",
            newline="",
            encoding="utf-8-sig",
        ) as file:
            reader = csv.DictReader(file)

            for line_number, row in enumerate(reader, start=2):
                try:
                    source = (row.get("source") or "").strip()
                    reference = (
                        row.get("source_reference") or ""
                    ).strip()

                    if not source or not reference:
                        raise ValueError(
                            "Source and source_reference are required."
                        )

                    schedule = FlightSchedule(
                        airline_name=row["airline_name"],
                        airline_iata=row.get("airline_iata") or None,
                        airline_icao=row.get("airline_icao") or None,
                        flight_number=row.get("flight_number") or None,
                        callsign=row.get("callsign") or None,
                        departure_icao=row["departure_icao"].strip().upper(),
                        arrival_icao=row["arrival_icao"].strip().upper(),
                        departure_time_local=self.parse_time(
                            row.get("departure_time_local")
                        ),
                        arrival_time_local=self.parse_time(
                            row.get("arrival_time_local")
                        ),
                        arrival_day_offset=(
                            int(row["arrival_day_offset"])
                            if row.get("arrival_day_offset")
                            else None
                        ),
                        aircraft_icao=row.get("aircraft_icao") or None,
                        aircraft_name=row.get("aircraft_name") or None,
                        service_type=row.get("service_type") or "unknown",
                        operating_days=self.parse_days(
                            row.get("operating_days")
                        ),
                        valid_from=self.parse_date(
                            row.get("valid_from")
                        ),
                        valid_until=self.parse_date(
                            row.get("valid_until")
                        ),
                        source=source,
                        source_reference=reference,
                        last_verified=self.parse_datetime(
                            row.get("last_verified")
                        ),
                        status=row.get("status") or "unverified",
                    )

                    schedules.append(schedule)

                except (
                    KeyError,
                    ValueError,
                    TypeError,
                    ValidationError,
                ) as exc:
                    raise ValueError(
                        f"Invalid schedule CSV row {line_number}: {exc}"
                    ) from exc

        logger.info(
            "SCHEDULE CSV LOADED | path=%s | records=%d",
            self.csv_path,
            len(schedules),
        )

        return schedules
