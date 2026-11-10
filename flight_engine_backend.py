from __future__ import annotations

import multiprocessing
import os
import sys
from pathlib import Path

import uvicorn

from app.core.logging import configure_logging


def get_application_root() -> Path:
    if getattr(sys, "frozen", False):
        executable_dir = Path(sys.executable).resolve().parent

        if (
            executable_dir.name.lower() == "dist"
            and (executable_dir.parent / "frontend").is_dir()
        ):
            return executable_dir.parent

        return executable_dir

    return Path(__file__).resolve().parent


def main() -> None:
    multiprocessing.freeze_support()

    root = get_application_root()

    os.chdir(root)

    database_path = root / "flightengine.db"

    if not database_path.is_file():
        raise FileNotFoundError(
            f"FlightEngine database not found: {database_path}"
        )

    os.environ["DATABASE_URL"] = (
        f"sqlite:///{database_path.as_posix()}"
    )

    print(
        f"[FlightEngine Backend] Database: {database_path}",
        flush=True,
    )

    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    configure_logging(
        level=os.getenv("FLIGHTENGINE_LOG_LEVEL", "INFO"),
        log_directory=root / "logs",
    )

    print(
        "[FlightEngine Backend] Starting FastAPI...",
        flush=True,
    )

    print(
        f"[FlightEngine Backend] Application root: {root}",
        flush=True,
    )

    print(
        f"[FlightEngine Backend] Log directory: {root / 'logs'}",
        flush=True,
    )

    # Import FastAPI after logging has been configured.
    from app.main import app

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="warning",
        access_log=False,
        reload=False,
        workers=1,
    )


if __name__ == "__main__":
    main()
