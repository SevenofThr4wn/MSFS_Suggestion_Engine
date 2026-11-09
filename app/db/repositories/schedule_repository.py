
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models.flight_schedule import FlightScheduleRecord
from app.schemas.schedule import FlightSchedule


logger = get_logger("schedules.repository")


class ScheduleRepository:
    """Persistence and retrieval for airline schedules."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_for_route(
        self,
        departure_icao: str,
        arrival_icao: str,
        airline_icao: str | None = None,
        limit: int = 500,
    ) -> list[FlightSchedule]:
        """Retrieve schedules for an exact airport pair."""
        departure = departure_icao.strip().upper()
        arrival = arrival_icao.strip().upper()

        statement = select(FlightScheduleRecord).where(
            FlightScheduleRecord.departure_icao == departure,
            FlightScheduleRecord.arrival_icao == arrival,
        )

        if airline_icao:
            statement = statement.where(
                FlightScheduleRecord.airline_icao
                == airline_icao.strip().upper()
            )

        statement = statement.order_by(
            FlightScheduleRecord.airline_name,
            FlightScheduleRecord.flight_number,
            FlightScheduleRecord.id,
        ).limit(limit)

        records = self.session.scalars(statement).all()

        logger.debug(
            "SCHEDULE QUERY | %s -> %s | airline=%s | records=%d",
            departure,
            arrival,
            airline_icao or "ANY",
            len(records),
        )

        return [self.to_schema(record) for record in records]

    def upsert(
        self,
        schedule: FlightSchedule,
    ) -> FlightScheduleRecord:
        """Insert or update a schedule using its source identity."""
        if not schedule.source or not schedule.source_reference:
            raise ValueError(
                "Schedules must have a source and source_reference."
            )

        statement = select(FlightScheduleRecord).where(
            FlightScheduleRecord.source == schedule.source,
            FlightScheduleRecord.source_reference
            == schedule.source_reference,
        )

        record = self.session.scalar(statement)

        if record is None:
            record = FlightScheduleRecord(
                source=schedule.source,
                source_reference=schedule.source_reference,
            )
            self.session.add(record)

        values = schedule.model_dump(mode="python")

        for field, value in values.items():
            setattr(
                record,
                field,
                value.value if hasattr(value, "value") else value,
            )

        self.session.flush()
        return record

    @staticmethod
    def to_schema(
        record: FlightScheduleRecord,
    ) -> FlightSchedule:
        """Convert a database record to the public schedule schema."""
        return FlightSchedule(
            airline_name=record.airline_name,
            airline_iata=record.airline_iata,
            airline_icao=record.airline_icao,
            flight_number=record.flight_number,
            callsign=record.callsign,
            departure_icao=record.departure_icao,
            arrival_icao=record.arrival_icao,
            departure_time_local=record.departure_time_local,
            arrival_time_local=record.arrival_time_local,
            arrival_day_offset=record.arrival_day_offset,
            aircraft_icao=record.aircraft_icao,
            aircraft_name=record.aircraft_name,
            service_type=record.service_type,
            operating_days=record.operating_days or [],
            valid_from=record.valid_from,
            valid_until=record.valid_until,
            source=record.source,
            source_reference=record.source_reference,
            last_verified=record.last_verified,
            status=record.status,
        )
