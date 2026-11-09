from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base


ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):

    def __init__(
        self,
        model: type[ModelT],
        session: Session,
    ):
        self.model = model
        self.session = session

    def get_by_id(self, record_id: int) -> ModelT | None:
        return self.session.get(self.model, record_id)

    def get_all(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ModelT]:
        if limit < 1 or offset < 0:
            raise ValueError("Invalid pagination parameters")

        stmt = (
            select(self.model)
            .order_by(self.model.id)
            .offset(offset)
            .limit(limit)
        )

        return list(self.session.scalars(stmt).all())

    def create(self, obj: ModelT) -> ModelT:
        self.session.add(obj)
        self.session.flush()
        return obj

    def delete(self, obj: ModelT) -> None:
        self.session.delete(obj)

    def exists(self, record_id: int) -> bool:
        return self.get_by_id(record_id) is not None
