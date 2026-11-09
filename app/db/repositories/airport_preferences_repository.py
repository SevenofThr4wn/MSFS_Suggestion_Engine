from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.airport_preferences import AirportPreferences


class AirportPreferencesRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, code: str) -> AirportPreferences | None:
        return self.session.get(
            AirportPreferences,
            code.strip().upper(),
        )

    def list_addon_codes(self) -> set[str]:
        stmt = select(AirportPreferences.icao_code).where(
            AirportPreferences.has_addon_scenery.is_(True)
        )

        return set(self.session.scalars(stmt).all())

    def list_all(self) -> list[AirportPreferences]:
        return list(
            self.session.scalars(
                select(AirportPreferences)
            ).all()
        )

    def save(
        self,
        code: str,
        *,
        has_addon_scenery: bool,
        scenery_developer: str | None = None,
        is_favourite: bool = False,
    ) -> AirportPreferences:

        code = code.strip().upper()

        record = self.get(code)

        if record is None:
            record = AirportPreferences(icao_code=code)
            self.session.add(record)

        record.has_addon_scenery = has_addon_scenery
        record.scenery_developer = scenery_developer
        record.is_favourite = is_favourite

        self.session.flush()
        return record
