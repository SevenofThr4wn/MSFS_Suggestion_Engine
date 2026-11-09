
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models.aircraft import Aircraft
from app.db.models.route_catalog import RouteCatalogEntry


class RouteCatalogRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_routes(
        self,
        departure_code: str | None = None,
        arrival_code: str | None = None,
        real_world_only: bool = False,
    ) -> list[RouteCatalogEntry]:

        stmt = (
            select(RouteCatalogEntry)
            .options(
                selectinload(RouteCatalogEntry.aircraft),
                selectinload(RouteCatalogEntry.airline),
            )
            .where(RouteCatalogEntry.is_active.is_(True))
        )

        if departure_code:
            stmt = stmt.where(
                RouteCatalogEntry.departure_icao
                == departure_code.upper()
            )

        if arrival_code:
            stmt = stmt.where(
                RouteCatalogEntry.arrival_icao
                == arrival_code.upper()
            )

        if real_world_only:
            stmt = stmt.where(
                RouteCatalogEntry.is_real_world_route.is_(
                    True
                )
            )

        return list(
            self.session.scalars(
                stmt.order_by(RouteCatalogEntry.id)
            ).all()
        )

    def list_aircraft(
        self,
        owned_only: bool = True,
        aircraft_id: int | None = None,
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
