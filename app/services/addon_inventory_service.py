from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from app.schemas.addon import (
    AddonCategory,
    AddonInventoryResponse,
    AddonPackage,
    AddonScanRoot,
    DetectionMethod,
)

from app.services.addon_metadata_service import enrich_packages

from app.services.addon_utility_service import (
    detect_external_utilities,
)

logger = logging.getLogger("flightengine.addons")

PACKAGE_FOLDERS = ("Community", "Community 2024")
MAX_MANIFEST_BYTES = 1_000_000
MAX_PACKAGES_PER_ROOT = 10_000

PACKAGE_PATH_PATTERN = re.compile(
    r'^\s*InstalledPackagesPath\s+"([^"]+)"',
    re.IGNORECASE | re.MULTILINE,
)


def read_installed_packages_path(
    config_file: Path,
) -> Path | None:
    try:
        content = config_file.read_text(
            encoding="utf-8-sig",
            errors="replace",
        )

        match = PACKAGE_PATH_PATTERN.search(content)

        if not match:
            return None

        value = os.path.expandvars(
            match.group(1).strip()
        )

        if not value:
            return None

        return Path(value).expanduser()

    except OSError:
        return None


def get_default_package_roots() -> list[tuple[str, Path]]:
    candidates: list[tuple[str, Path]] = []

    appdata = os.getenv("APPDATA")
    localappdata = os.getenv("LOCALAPPDATA")

    installations: list[tuple[str, Path]] = []

    if appdata:
        installations.append((
            "Steam",
            Path(appdata) / "Microsoft Flight Simulator 2024",
        ))

    if localappdata:
        installations.append((
            "Microsoft Store",
            Path(localappdata)
            / "Packages"
            / "Microsoft.Limitless_8wekyb3d8bbwe"
            / "LocalCache",
        ))

    for label, installation in installations:
        configured = read_installed_packages_path(
            installation / "UserCfg.opt"
        )

        if configured is not None:
            packages_root = configured
        else:
            packages_root = installation / "Packages"

        for folder in PACKAGE_FOLDERS:
            candidates.append((
                f"{label} {folder}",
                packages_root / folder,
            ))

    return candidates


def get_custom_package_roots() -> list[tuple[str, Path]]:
    raw = os.getenv("FLIGHTENGINE_ADDON_PATHS", "")

    roots: list[tuple[str, Path]] = []

    for index, entry in enumerate(
        raw.split(os.pathsep),
        start=1,
    ):
        value = entry.strip().strip('"')

        if not value:
            continue

        expanded = os.path.expandvars(value)

        roots.append((
            f"Custom {index}",
            Path(expanded).expanduser(),
        ))

    return roots


def resolve_roots(
    configured_roots: list[tuple[str, Path]] | None = None,
) -> list[tuple[str, Path]]:
    candidates = (
        configured_roots
        if configured_roots is not None
        else get_default_package_roots()
        + get_custom_package_roots()
    )

    roots: list[tuple[str, Path]] = []
    seen: set[str] = set()

    for label, path in candidates:
        try:
            resolved = path.resolve(strict=False)
        except (OSError, RuntimeError):
            continue

        key = os.path.normcase(str(resolved))

        if key in seen:
            continue

        seen.add(key)
        roots.append((label, resolved))

    return roots


def read_package_manifest(
    directory: Path,
) -> dict | None:
    manifest = directory / "manifest.json"

    try:
        if not manifest.is_file():
            return None

        if manifest.stat().st_size > MAX_MANIFEST_BYTES:
            return None

        with manifest.open(
            "r",
            encoding="utf-8-sig",
        ) as handle:
            result = json.load(handle)

        return result if isinstance(result, dict) else None

    except (OSError, ValueError, UnicodeError):
        return None


def classify_package(
    package_id: str,
    title: str,
    content_type: str,
) -> AddonCategory:
    name = f"{package_id} {title}".casefold()
    kind = content_type.casefold().strip()

    if "fsltl" in name:
        return AddonCategory.TRAFFIC

    if any(
        marker in name
        for marker in ("gsx", "couatl", "fsdreamteam")
    ):
        return AddonCategory.UTILITY

    if kind == "livery":
        return AddonCategory.LIVERY

    if kind == "aircraft":
        return AddonCategory.AIRCRAFT

    if kind == "scenery":
        if any(
            marker in name
            for marker in ("airport", "airfield")
        ):
            return AddonCategory.AIRPORT

        return AddonCategory.SCENERY

    if "livery" in name or "repaint" in name:
        return AddonCategory.LIVERY

    if "aircraft" in name:
        return AddonCategory.AIRCRAFT

    if "airport" in name or "airfield" in name:
        return AddonCategory.AIRPORT

    if "scenery" in name:
        return AddonCategory.SCENERY

    return AddonCategory.UNKNOWN


def inspect_package(
    directory: Path,
    source: str,
) -> AddonPackage | None:
    manifest = read_package_manifest(directory)

    if manifest is None:
        name = directory.name.casefold()

        if "fsltl" in name:
            category = AddonCategory.TRAFFIC
        elif any(
            value in name
            for value in ("gsx", "couatl")
        ):
            category = AddonCategory.UTILITY
        else:
            return None

        return AddonPackage(
            package_id=directory.name,
            name=directory.name,
            category=category,
            source=source,
            detection_method=DetectionMethod.FOLDER_NAME,
        )

    title = str(
        manifest.get("title") or directory.name
    )

    content_type = str(
        manifest.get("content_type") or ""
    )

    version = manifest.get("package_version")
    creator = manifest.get("creator")

    return AddonPackage(
        package_id=directory.name,
        name=title,
        category=classify_package(
            directory.name,
            title,
            content_type,
        ),
        content_type=content_type or None,
        version=str(version) if version is not None else None,
        creator=str(creator) if creator is not None else None,
        source=source,
        detection_method=DetectionMethod.MANIFEST,
    )


class AddonInventoryService:
    def __init__(
        self,
        cache_seconds: int = 300,
        roots: list[tuple[str, Path]] | None = None,
    ) -> None:
        self.cache_seconds = cache_seconds
        self._roots = roots
        self._inventory: AddonInventoryResponse | None = None
        self._cache_time = 0.0
        self._lock = threading.Lock()

    def scan(
        self,
        refresh: bool = False,
    ) -> AddonInventoryResponse:
        with self._lock:
            now = time.monotonic()

            if (
                not refresh
                and self._inventory is not None
                and now - self._cache_time < self.cache_seconds
            ):
                return self._inventory.model_copy(
                    update={"cached": True}
                )

            packages: list[AddonPackage] = []
            root_results: list[AddonScanRoot] = []
            warnings: list[str] = []

            seen_directories: set[str] = set()

            for label, root in resolve_roots(self._roots):
                available = root.is_dir()
                count = 0

                if not available:
                    root_results.append(
                        AddonScanRoot(
                            label=label,
                            available=False,
                        )
                    )
                    continue

                try:
                    directories = []

                    if (root / "manifest.json").is_file():
                        directories.append(root)
                    else:
                        with os.scandir(root) as entries:
                            for entry in entries:
                                if len(directories) >= MAX_PACKAGES_PER_ROOT:
                                    warnings.append(
                                        f"{label}: package scan limit reached."
                                    )
                                    break

                                try:
                                    if entry.is_dir(
                                        follow_symlinks=True
                                    ):
                                        directories.append(Path(entry.path))
                                except OSError:
                                    continue

                    for directory in directories:
                        try:
                            resolved = directory.resolve()
                            identity = os.path.normcase(
                                str(resolved)
                            )

                            if identity in seen_directories:
                                continue

                            addon = inspect_package(
                                resolved,
                                label,
                            )

                            if addon is None:
                                continue

                            seen_directories.add(identity)
                            packages.append(addon)
                            count += 1

                        except (OSError, RuntimeError):
                            continue

                except OSError as exc:
                    logger.warning(
                        "ADDON SCAN FAILED | root=%s | error=%s",
                        label,
                        type(exc).__name__,
                    )
                    warnings.append(
                        f"{label}: directory could not be read."
                    )

                root_results.append(
                    AddonScanRoot(
                        label=label,
                        available=True,
                        packages_found=count,
                    )
                )

            packages.sort(
                key=lambda item: (
                    item.category.value,
                    item.name.casefold(),
                )
            )

            totals = Counter(
                package.category.value
                for package in packages
            )

            variants, airport_candidates, utilities = enrich_packages(
                packages=packages,
                roots=resolve_roots(self._roots),
            )

            utilities.extend(detect_external_utilities())

            utilities = list({
                (item.name, item.component, item.evidence): item
                for item in utilities
            }.values())

            inventory = AddonInventoryResponse(
                scanned_at=datetime.now(timezone.utc),
                total_packages=len(packages),
                cached=False,
                categories=dict(totals),
                roots=root_results,
                packages=packages,
                aircraft_variants=variants,
                airport_candidates=airport_candidates,
                utilities=utilities,
                warnings=warnings
            )

            self._inventory = inventory
            self._cache_time = time.monotonic()

            logger.info(
                "ADDON SCAN COMPLETE | roots=%d | packages=%d",
                len(root_results),
                len(packages),
            )

            return inventory
