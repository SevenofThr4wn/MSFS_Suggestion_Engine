from dataclasses import asdict, dataclass, field
from typing import Literal

Suitability = Literal[
    "preliminary_pass",
    "rejected",
    "indeterminate",
]

@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: str
    airport_icao: str | None
    message: str
    observed: float | str | None = None
    required: float | str | None = None
    unit: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ValidationOutcome:
    status: str
    issues: tuple[ValidationIssue, ...]
    departure_runway: str | None
    arrival_runway: str | None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "issues": [
                issue.to_dict()
                for issue in self.issues
            ],
            "departure_runway": self.departure_runway,
            "arrival_runway": self.arrival_runway,
        }

@dataclass(frozen=True)
class FlyabilityResult:
    score: float
    status: str
    breakdown: dict[str, float]
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    evidence_coverage: dict[str, bool] = field(
        default_factory=dict
    )
    personal_feedback_available: bool = False