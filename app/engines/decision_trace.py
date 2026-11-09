import logging
import uuid

from dataclasses import dataclass, field
from datetime import datetime, timezone


logger = logging.getLogger(
    "app.recommendations.decision_trace"
)


@dataclass
class DecisionTrace:
    request_id: str = field(
        default_factory=lambda: str(uuid.uuid4())
    )

    events: list[dict] = field(
        default_factory=list
    )

    max_events: int = 500

    def record(
        self,
        stage: str,
        action: str,
        *,
        code: str | None = None,
        details: dict | None = None,
    ):
        # --------------------------------------------------
        # Construct Decision Trace Entry
        # --------------------------------------------------

        entry = {
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "stage": stage,
            "action": action,
            "code": code,
            "details": details or {},
        }

        # --------------------------------------------------
        # Store Event Within Configured Limit
        # --------------------------------------------------

        if len(self.events) < self.max_events:
            self.events.append(entry)

        # --------------------------------------------------
        # Write Structured Log Entry
        # --------------------------------------------------

        logger.info(
            "request_id=%s stage=%s action=%s "
            "code=%s details=%s",
            self.request_id,
            stage,
            action,
            code,
            entry["details"],
        )

    def to_dict(self):
        return {
            "request_id": self.request_id,
            "events": self.events,
            "truncated": (
                len(self.events) >= self.max_events
            ),
        }
