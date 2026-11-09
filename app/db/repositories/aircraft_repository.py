from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.aircraft import Aircraft


class AircraftRepository:

    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, aircraft_id: int) -> Aircraft | None:
        return self.session.get(Aircraft, aircraft_id)

    def get_by_icao(self, icao_code: str) -> list[Aircraft]:
        stmt = (
            select(Aircraft)
            .where(Aircraft.icao_code == icao_code.upper())
            .order_by(Aircraft.id)
        )

        return list(self.session.scalars(stmt).all())

    def list_aircraft(
        self,
        *,
        category: str | None = None,
        owned_only: bool = False,
        icao_code: str | None = None,
    ) -> list[Aircraft]:

        stmt = select(Aircraft)

        if category:
            stmt = stmt.where(
                Aircraft.category == category.lower()
            )

        if owned_only:
            stmt = stmt.where(Aircraft.is_owned.is_(True))

        if icao_code:
            stmt = stmt.where(
                Aircraft.icao_code == icao_code.upper()
            )

        stmt = stmt.order_by(Aircraft.id)

        return list(self.session.scalars(stmt).all())
