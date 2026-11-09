from __future__ import annotations

import os
from pathlib import Path

from app.schemas.addon import UtilityComponent


UTILITY_CONFIG = {
    "FLIGHTENGINE_GSX_PATH": ("GSX", "external_installation"),
    "FLIGHTENGINE_FSLTL_INJECTOR_PATH": ("FSLTL", "injector"),
}


def detect_external_utilities() -> list[UtilityComponent]:
    results: list[UtilityComponent] = []

    for variable, (name, component) in UTILITY_CONFIG.items():
        configured = os.getenv(variable)

        if not configured:
            continue

        path = Path(
            os.path.expandvars(configured)
        ).expanduser()

        if not path.exists():
            continue

        results.append(
            UtilityComponent(
                name=name,
                component=component,
                detected=True,
                evidence="configured_path_exists",
            )
        )

    return results
