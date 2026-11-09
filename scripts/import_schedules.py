from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import inspect

from app.core.logging import get_logger
from app.db.models.flight_schedule import FlightScheduleRecord
from app.db.repositories.schedule_repository import (
    ScheduleRepository,
)
from app.db.session import SessionLocal, engine
from app.providers.schedules.local_provider import LocalScheduleProvider


logger = get_logger("schedules.import")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import source-backed airline schedules."
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=Path("data/flight_schedules.csv"),
    )
    args = parser.parse_args()

    # Validate the entire input before any database writes.
    schedules = LocalScheduleProvider(args.file).load()

    if not schedules:
        print("No schedules to import.")
        return

    if "aircraft" not in inspect(engine).get_table_names():
        raise RuntimeError(
            "Connected database has no aircraft table. "
            "Check DATABASE_URL before importing schedules."
        )

    # Creates only this table if it is absent.
    FlightScheduleRecord.__table__.create(
        bind=engine,
        checkfirst=True,
    )

    with SessionLocal.begin() as db:
        repository = ScheduleRepository(db)

        for schedule in schedules:
            repository.upsert(schedule)

    logger.info(
        "SCHEDULE IMPORT COMPLETE | imported=%d",
        len(schedules),
    )

    print(f"Imported or updated {len(schedules)} schedules.")


if __name__ == "__main__":
    main()
