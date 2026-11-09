from __future__ import annotations

import configparser
import json
import os
import re
from pathlib import Path

from app.schemas.addon import (
    AddonPackage,
    AircraftVariant,
    AirportCandidate,
    UtilityComponent,
)

MAX_CFG_BYTES = 512_000
MAX_LAYOUT_BYTES = 8_000_000
MAX_CONFIGS_PER_PACKAGE = 300

ICAO_PATTERN = re.compile(r"^[A-Z0-9]{2,4}$")
AIRPORT_PATH_PATTERN = re.compile(
    r"(?:^|[/\\])airport[-_]([a-z0-9]{4})(?:[/\\._-]|$)",
    re.IGNORECASE,
)


def read_configuration(path: Path) -> configparser.ConfigParser | None:
    try:
        if not path.is_file() or path.stat().st_size > MAX_CFG_BYTES:
            return None

        config = configparser.ConfigParser(
            interpolation=None,
            strict=False,
            inline_comment_prefixes=(";",),
        )

        config.read(path, encoding="utf-8-sig")
        return config
    except (
        OSError,
        UnicodeError,
        configparser.Error,
    ):
        return None


def normalized_icao(value: str | None) -> str | None:
    if not value:
        return None

    code = value.strip().strip('"').strip("'").upper()

    return code if ICAO_PATTERN.fullmatch(code) else None


def get_value(
    config: configparser.ConfigParser,
    section: str,
    option: str,
) -> str | None:
    if not config.has_section(section):
        return None

    value = config.get(section, option, fallback="").strip()

    return value.strip('"').strip("'") or None


def parse_selectable(value: str | None) -> bool | None:
    if value is None:
        return None

    if value.casefold() in ("1", "true", "yes"):
        return True

    if value.casefold() in ("0", "false", "no"):
        return False

    return None


def find_aircraft_configs(package: Path) -> list[Path]:
    results: list[Path] = []

    try:
        simobject_roots = [
            child
            for child in package.iterdir()
            if child.is_dir() and child.name.casefold() == "simobjects"
        ]
    except OSError:
        return results

    for root in simobject_roots:
        try:
            for base, directories, files in os.walk(root):
                depth = len(Path(base).relative_to(root).parts)

                if depth >= 4:
                    directories[:] = []

                for filename in files:
                    if filename.casefold() not in (
                        "aircraft.cfg",
                        "livery.cfg",
                    ):
                        continue

                    results.append(Path(base) / filename)

                    if len(results) >= MAX_CONFIGS_PER_PACKAGE:
                        return results
        except OSError:
            continue

    return results


def extract_aircraft_variants(
    package: Path,
    package_id: str,
) -> list[AircraftVariant]:
    variants: list[AircraftVariant] = []

    for path in find_aircraft_configs(package):
        config = read_configuration(path)

        if config is None:
            continue

        aircraft_icao = normalized_icao(
            get_value(config, "GENERAL", "icao_type_designator")
        )

        is_livery = (
            path.name.casefold() == "livery.cfg"
            or config.has_section("LIVERY")
        )

        sections = [
            section
            for section in config.sections()
            if re.fullmatch(
                r"FLTSIM\.\d+",
                section,
                flags=re.IGNORECASE,
            )
        ]

        for section in sections:
            title = (
                get_value(config, section, "title")
                or path.parent.name
            )

            airline_icao = normalized_icao(
                get_value(config, section, "icao_airline")
            )

            variant = AircraftVariant(
                package_id=package_id,
                title=title,
                aircraft_icao=aircraft_icao,
                airline_icao=airline_icao,
                airline_name=get_value(
                    config,
                    section,
                    "atc_airline",
                ),
                registration=get_value(
                    config,
                    section,
                    "atc_id",
                ),
                user_selectable=parse_selectable(
                    get_value(
                        config,
                        section,
                        "isUserSelectable",
                    )
                ),
                is_livery=is_livery,
            )

            variants.append(variant)

    unique: dict[tuple[str, str, str, str], AircraftVariant] = {}

    for variant in variants:
        key = (
            variant.package_id,
            variant.title,
            variant.aircraft_icao or "",
            variant.airline_icao or "",
        )

        unique[key] = variant

    return list(unique.values())


def extract_airport_candidates(
    package: Path,
    package_id: str,
) -> list[AirportCandidate]:
    layout = package / "layout.json"

    try:
        if (
            not layout.is_file()
            or layout.stat().st_size > MAX_LAYOUT_BYTES
        ):
            return []

        with layout.open("r", encoding="utf-8-sig") as handle:
            data = json.load(handle)

    except (OSError, ValueError, UnicodeError):
        return []

    entries = data.get("content", []) if isinstance(data, dict) else []

    if not isinstance(entries, list):
        return []

    candidates: dict[str, AirportCandidate] = {}

    for entry in entries[:20_000]:
        if not isinstance(entry, dict):
            continue

        path = entry.get("path")

        if not isinstance(path, str):
            continue

        match = AIRPORT_PATH_PATTERN.search(path)

        if not match:
            continue

        icao = match.group(1).upper()

        candidates[icao] = AirportCandidate(
            package_id=package_id,
            icao=icao,
            evidence="layout_filename",
            verified=False,
        )

    return list(candidates.values())


def detect_utility(
    package_id: str,
    package_name: str,
) -> UtilityComponent | None:
    name = f"{package_id} {package_name}".casefold()

    if "fsltl" in name:
        if "injector" in name:
            component = "injector"
        elif any(value in name for value in ("base", "model", "traffic")):
            component = "base_models"
        else:
            component = "unknown"

        return UtilityComponent(
            name="FSLTL",
            component=component,
            detected=True,
            evidence="package_identifier",
        )

    if any(
        value in name
        for value in ("fsdreamteam-gsx", "gsx-pro", "couatl")
    ):
        return UtilityComponent(
            name="GSX",
            component="package",
            detected=True,
            evidence="package_identifier",
        )

    return None


def enrich_packages(
    packages: list[AddonPackage],
    roots: list[tuple[str, Path]],
) -> tuple[
    list[AircraftVariant],
    list[AirportCandidate],
    list[UtilityComponent],
]:
    variants: list[AircraftVariant] = []
    airports: list[AirportCandidate] = []
    utilities: list[UtilityComponent] = []

    package_lookup = {
        (package.source, package.package_id): package
        for package in packages
    }

    seen_directories: set[Path] = set()

    for label, root in roots:
        if not root.is_dir():
            continue

        try:
            if (root / "manifest.json").is_file():
                directories = [root]
            else:
                directories = [
                    child
                    for child in root.iterdir()
                    if child.is_dir()
                ]
        except OSError:
            continue

        for directory in directories:
            try:
                resolved = directory.resolve()
            except (OSError, RuntimeError):
                continue

            if resolved in seen_directories:
                continue

            package = package_lookup.get(
                (label, resolved.name)
            )

            if package is None:
                package = package_lookup.get(
                    (label, directory.name)
                )

            if package is None:
                continue

            seen_directories.add(resolved)

            variants.extend(
                extract_aircraft_variants(
                    resolved,
                    package.package_id,
                )
            )

            airports.extend(
                extract_airport_candidates(
                    resolved,
                    package.package_id,
                )
            )

            utility = detect_utility(
                package.package_id,
                package.name,
            )

            if utility is not None:
                utilities.append(utility)

    variants.sort(
        key=lambda value: (
            value.aircraft_icao or "",
            value.airline_icao or "",
            value.title,
        )
    )

    airports.sort(
        key=lambda value: (
            value.icao,
            value.package_id,
        )
    )

    utilities.sort(
        key=lambda value: (
            value.name,
            value.component,
        )
    )

    return variants, airports, utilities
