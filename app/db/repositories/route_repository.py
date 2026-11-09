from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models.aircraft import Aircraft
from app.db.models.airport import Airport
from app.db.models.route import Route

class RouteRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_routes(
            self, 
            departure_code: str | None = None,
            arrival_code: str | None = None,
            real_world_only: bool = False) -> list[Route]:
        stmt = (
            select(Route)
            .options(
                selectinload(Route.departure_airport),
                selectinload(Route.arrival_airport),
                selectinload(Route.airline),
                selectinload(Route.aircraft)
            )
            .where(Route.is_active.is_(True))
        )

        if real_world_only:
            stmt = stmt.where(
                Route.is_real_world_route.is_(True)
            )

        if departure_code:
            stmt = stmt.join(
                Airport,
                Route.departure_airport_id == Airport.id
            ).where(
                (Airport.icao_code == departure_code)
                | (Airport.iata_code == departure_code)
            )

        if arrival_code:
            arrival = Airport.__table__.alias("arrival")

            stmt = stmt.join(
                arrival,
                Route.arrival_airport_id == arrival.c.id,
            ).where(
                (arrival.c.icao_code == arrival_code)
                | (arrival.c.iata_code == arrival_code)
            )

        return list(
            self.session.scalars(
                stmt.order_by(Route.id)
            ).all()
        )

    def list_airports(
            self,
            limit: int = 100,
    ) -> list[Airport]:

        stmt = (
            select(Airport)
            .options(selectinload(Airport.runways))
            .order_by(Airport.icao_code)
            .limit(limit)
        )

        return list(self.session.scalars(stmt).all())

    def list_aircraft(
            self,
            owned_only: bool = True,
            aircraft_id: int | None = None
    ) -> list[Aircraft]:

        stmt = select(Aircraft)

        if owned_only:
            stmt = stmt.where(Aircraft.is_owned.is_(True))

        if aircraft_id is not None:
            stmt = stmt.where(Aircraft.id == aircraft_id)

        return list(
            self.session.scalars(
                stmt.order_by(Aircraft.id)
            ).all()
        )

    def get_airport_by_code(
            self, 
            code: str
        ) -> Airport | None:
            from sqlalchemy import or_

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
            )

            return self.session.scalars(stmt).first()