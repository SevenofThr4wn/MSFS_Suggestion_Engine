from __future__ import annotations

from app.schemas.addon import (
    AddonCategory,
    AddonInventoryResponse,
)
from app.schemas.addon_compatibility import (
    AddonCompatibilityRequest,
    AddonCompatibilityResponse,
    CompatibilityCheck,
    CompatibilityStatus,
)


class AddonCompatibilityService:
    def __init__(
        self,
        inventory: AddonInventoryResponse,
    ) -> None:
        self.inventory = inventory

        self.packages = {
            package.package_id.casefold(): package
            for package in inventory.packages
        }

        self.has_scan_coverage = any(
            root.available
            for root in inventory.roots
        )

    @staticmethod
    def unknown(explanation: str) -> CompatibilityCheck:
        return CompatibilityCheck(
            status=CompatibilityStatus.UNKNOWN,
            explanation=explanation,
        )

    def not_found(self, label: str) -> CompatibilityCheck:
        if not self.has_scan_coverage:
            return self.unknown(
                f"Cannot determine {label}: no add-on scan roots are available."
            )

        return CompatibilityCheck(
            status=CompatibilityStatus.NOT_DETECTED,
            explanation=(
                f"No matching {label} was found in the scanned inventory. "
                "This does not prove it is uninstalled."
            ),
        )

    def aircraft_check(
        self,
        aircraft_icao: str | None,
    ) -> CompatibilityCheck:
        if not aircraft_icao:
            return self.unknown(
                "No aircraft ICAO code was supplied."
            )

        matches = []

        for variant in self.inventory.aircraft_variants:
            if variant.is_livery:
                continue

            if variant.user_selectable is False:
                continue

            if variant.aircraft_icao != aircraft_icao:
                continue

            package = self.packages.get(
                variant.package_id.casefold()
            )

            if package is None:
                continue

            if package.category != AddonCategory.AIRCRAFT:
                continue

            matches.append(variant)

        if not matches:
            return self.not_found(
                f"flyable aircraft {aircraft_icao}"
            )

        return CompatibilityCheck(
            status=CompatibilityStatus.DETECTED,
            package_ids=sorted({
                variant.package_id
                for variant in matches
            }),
            evidence=["aircraft_cfg_icao"],
            explanation=(
                f"An aircraft package declares type {aircraft_icao}. "
                "Simulator availability has not been verified."
            ),
        )

    def livery_check(
        self,
        aircraft_icao: str | None,
        airline_icao: str | None,
    ) -> CompatibilityCheck:
        if not aircraft_icao or not airline_icao:
            return self.unknown(
                "Aircraft and airline ICAO codes are required "
                "for an exact livery match."
            )

        matches = []

        incomplete = False

        for variant in self.inventory.aircraft_variants:
            if not variant.is_livery:
                continue

            package = self.packages.get(
                variant.package_id.casefold()
            )

            if (
                package is None
                or package.category != AddonCategory.LIVERY
            ):
                continue

            if variant.airline_icao != airline_icao:
                continue

            if variant.aircraft_icao is None:
                incomplete = True
                continue

            if variant.aircraft_icao == aircraft_icao:
                matches.append(variant)

        if matches:
            return CompatibilityCheck(
                status=CompatibilityStatus.DETECTED,
                package_ids=sorted({
                    variant.package_id
                    for variant in matches
                }),
                evidence=[
                    "aircraft_cfg_icao",
                    "livery_airline_icao",
                ],
                explanation=(
                    f"Detected a {airline_icao} livery "
                    f"declaring aircraft type {aircraft_icao}."
                ),
            )

        if incomplete:
            return self.unknown(
                "Matching airline liveries exist, but their "
                "base aircraft types could not be established."
            )

        return self.not_found(
            f"{airline_icao} livery for {aircraft_icao}"
        )

    def scenery_check(
        self,
        airport_icao: str,
    ) -> CompatibilityCheck:
        candidates = [
            candidate
            for candidate in self.inventory.airport_candidates
            if candidate.icao == airport_icao
            and self.packages.get(
                candidate.package_id.casefold()
            ) is not None
            and self.packages[
                candidate.package_id.casefold()
            ].category in (
                AddonCategory.AIRPORT,
                AddonCategory.SCENERY,
            )
        ]

        if not candidates:
            return self.not_found(
                f"airport scenery for {airport_icao}"
            )

        package_ids = sorted({
            candidate.package_id
            for candidate in candidates
        })

        if any(candidate.verified for candidate in candidates):
            return CompatibilityCheck(
                status=CompatibilityStatus.DETECTED,
                package_ids=package_ids,
                evidence=sorted({
                    candidate.evidence
                    for candidate in candidates
                }),
                explanation=(
                    f"Verified scenery metadata identifies "
                    f"{airport_icao}."
                ),
            )

        return CompatibilityCheck(
            status=CompatibilityStatus.UNKNOWN,
            package_ids=package_ids,
            evidence=sorted({
                candidate.evidence
                for candidate in candidates
            }),
            explanation=(
                f"Found possible scenery for {airport_icao}, "
                "but airport coverage has not been verified."
            ),
        )

    def utility_check(
        self,
        name: str,
    ) -> CompatibilityCheck:
        matches = [
            utility
            for utility in self.inventory.utilities
            if utility.name.casefold() == name.casefold()
            and utility.detected
        ]

        if not matches:
            return self.not_found(name)

        return CompatibilityCheck(
            status=CompatibilityStatus.DETECTED,
            evidence=sorted({
                utility.evidence
                for utility in matches
            }),
            explanation=(
                f"{name} components were detected: "
                + ", ".join(sorted({
                    utility.component
                    for utility in matches
                }))
                + ". Operational status is not verified."
            ),
        )

    def evaluate(
        self,
        request: AddonCompatibilityRequest,
    ) -> AddonCompatibilityResponse:
        return AddonCompatibilityResponse(
            aircraft=self.aircraft_check(
                request.aircraft_icao
            ),
            livery=self.livery_check(
                request.aircraft_icao,
                request.airline_icao,
            ),
            departure_scenery=self.scenery_check(
                request.departure_icao
            ),
            arrival_scenery=self.scenery_check(
                request.arrival_icao
            ),
            gsx=self.utility_check("GSX"),
            fsltl=self.utility_check("FSLTL"),
            inventory_scanned_at=(
                self.inventory.scanned_at.isoformat()
            ),
            warnings=list(self.inventory.warnings),
        )
