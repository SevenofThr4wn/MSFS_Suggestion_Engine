from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class OperationsAssessment:
    """Result of evaluating route realism."""

    score: float | None
    verified_catalog_match: bool
    airline: str | None
    flight_number: str | None
    notes: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)