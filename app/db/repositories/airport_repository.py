from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.models.airport import Airport


class AirportRepository:

    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, airport_id: int) -> Airport | None:
        stmt = (
            select(Airport)
            .options(selectinload(Airport.runways))
            .where(Airport.id == airport_id)
        )

        return self.session.scalar(stmt)

    def get_by_code(self, code: str) -> Airport | None:
        normalized = code.strip().upper()

        stmt = (
            select(Airport)
            .options(selectinload(Airport.runways))
            .where(
                or_(
                    Airport.icao_code == normalized,
                    Airport.iata_code == normalized,
                )
            )
            .order_by(Airport.id)
        )

        return self.session.scalars(stmt).first()

    def search(
        self,
        *,
        query: str | None = None,
        country: str | None = None,
        addon_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[int, list[Airport]]:

        stmt = select(Airport)

        if query:
            pattern = f"%{query.strip()}%"

            stmt = stmt.where(
                or_(
                    Airport.name.ilike(pattern),
                    Airport.city.ilike(pattern),
                    Airport.icao_code.ilike(pattern),
                    Airport.iata_code.ilike(pattern),
                )
            )

        if country:
            stmt = stmt.where(
                Airport.country.ilike(country.strip())
            )

        if addon_only:
            stmt = stmt.where(
                Airport.has_addon_scenery.is_(True)
            )

        total = self.session.scalar(
            select(func.count()).select_from(
                stmt.order_by(None).subquery()
            )
        ) or 0

        stmt = (
            stmt
            .options(selectinload(Airport.runways))
            .order_by(Airport.name, Airport.id)
            .limit(limit)
            .offset(offset)
        )

        airports = list(self.session.scalars(stmt).all())

        return total, airports
