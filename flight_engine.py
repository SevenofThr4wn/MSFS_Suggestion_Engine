import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

from pathlib import Path


APP_NAME = "MSFS FlightEngine"
APP_VERSION = "0.2.0"

FRONTEND_PORT = 3000
BACKEND_PORT = 8000

BACKEND_URL = f"http://127.0.0.1:{BACKEND_PORT}"
FRONTEND_URL = f"http://127.0.0.1:{FRONTEND_PORT}"

STARTUP_TIMEOUT = 60

WINDOWS = sys.platform == "win32"

CREATE_PROCESS_GROUP = (
    subprocess.CREATE_NEW_PROCESS_GROUP if WINDOWS else 0
)


def get_project_root() -> Path:
    """
    Locate the FlightEngine project directory.

    Supports:
    - Running as a Python script.
    - Running a packaged executable from dist/.
    - Running a packaged executable in the project root.
    """

    if getattr(sys, "frozen", False):
        start_directory = Path(sys.executable).resolve().parent
    else:
        start_directory = Path(__file__).resolve().parent

    candidates = [
        start_directory,
        *start_directory.parents,
    ]

    for directory in candidates:
        if (
            (directory / "app").is_dir()
            and (directory / "frontend").is_dir()
        ):
            return directory

    raise FileNotFoundError(
        "Unable to locate the FlightEngine project root.\n"
        f"Executable location: {start_directory}\n"
        "Expected the 'app' and 'frontend' directories "
        "to exist in the project root."
    )


ROOT = get_project_root()

BACKEND_DIR = ROOT
FRONTEND_DIR = ROOT / "frontend"

BACKEND_EXE = (
    ROOT / "dist" / "FlightEngineBackend.exe"
)


def log(message: str):
    print(f"[FlightEngine] {message}", flush=True)


def log_environment():
    log(f"Application: {APP_NAME}")
    log(f"Version: {APP_VERSION}")
    log(f"Project root: {ROOT}")
    log(f"Frontend: {FRONTEND_DIR}")
    log(f"Backend: {BACKEND_DIR}")
    log(f"Packaged Backend: {BACKEND_EXE}")


def check_paths():
    required_directories = {
        "Backend": BACKEND_DIR / "app",
        "Frontend": FRONTEND_DIR,
        "Python environment": BACKEND_EXE.parent,
    }

    for name, path in required_directories.items():
        if not path.exists():
            raise RuntimeError(
                f"{name} directory missing: {path}"
            )

    if not BACKEND_EXE.is_file():
        raise RuntimeError(
            "Packaged backend executable missing.\n"
            f"Expected: {BACKEND_EXE}"
        )

    if not (FRONTEND_DIR / "package.json").is_file():
        raise RuntimeError(
            "Frontend package.json is missing."
        )

    if not (FRONTEND_DIR / ".next").is_dir():
        raise RuntimeError(
            "Next.js production build missing.\n"
            "Run 'npm run build' inside the frontend directory."
        )

    if not (FRONTEND_DIR / ".next" / "BUILD_ID").is_file():
        raise RuntimeError(
            "Next.js production build is incomplete.\n"
            "Run 'npm run build' inside the frontend directory."
        )

    if not (FRONTEND_DIR / "node_modules").is_dir():
        raise RuntimeError(
            "Frontend dependencies are missing.\n"
            "Run 'npm install' inside the frontend directory."
        )

    if shutil.which("npm.cmd" if WINDOWS else "npm") is None:
        raise RuntimeError(
            "Node.js/npm was not found in PATH.\n"
            "Install Node.js and ensure npm is available."
        )

    log("All application paths and dependencies verified.")


def port_available(port: int) -> bool:
    with socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    ) as sock:
        return sock.connect_ex(
            ("127.0.0.1", port)
        ) != 0


def wait_for_service(
    url: str,
    process: subprocess.Popen,
    timeout: int = STARTUP_TIMEOUT,
) -> bool:
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False

        try:
            with urllib.request.urlopen(
                url,
                timeout=2,
            ) as response:
                if response.status < 500:
                    return True

        except urllib.error.HTTPError as error:
            if error.code < 500:
                return True

        except (
            urllib.error.URLError,
            TimeoutError,
            OSError,
        ):
            pass

        time.sleep(0.5)

    return False

def start_backend() -> subprocess.Popen:
    log("Starting packaged FastAPI backend...")


    environment = os.environ.copy()

    return subprocess.Popen(
        [str(BACKEND_EXE)],
        cwd=ROOT,
        env=environment,
        creationflags=CREATE_PROCESS_GROUP,
    )


def start_frontend() -> subprocess.Popen:
    log("Starting Next.js frontend...")

    environment = os.environ.copy()

    environment["NODE_ENV"] = "production"
    environment["PORT"] = str(FRONTEND_PORT)
    environment["BACKEND_URL"] = BACKEND_URL

    npm_command = "npm.cmd" if WINDOWS else "npm"

    return subprocess.Popen(
        [
            npm_command,
            "run",
            "start",
        ],
        cwd=FRONTEND_DIR,
        env=environment,
        creationflags=CREATE_PROCESS_GROUP,
    )

def stop_process(process: subprocess.Popen | None):
    if process is None:
        return

    if process.poll() is not None:
        return

    try:
        if WINDOWS:
            subprocess.run(
                [
                    "taskkill",
                    "/PID",
                    str(process.pid),
                    "/T",
                    "/F",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )
        else:
            process.terminate()
            process.wait(timeout=10)

    except Exception:
        try:
            process.kill()
        except OSError:
            pass


def main():
    backend = None
    frontend = None

    try:
        log("=" * 55)
        log(f"Launching {APP_NAME} v{APP_VERSION}")
        log("=" * 55)

        log_environment()
        check_paths()

        # Validate available ports
        if not port_available(BACKEND_PORT):
            raise RuntimeError(
                f"Backend port {BACKEND_PORT} is already in use.\n"
                "Close any existing FastAPI instance."
            )

        if not port_available(FRONTEND_PORT):
            raise RuntimeError(
                f"Frontend port {FRONTEND_PORT} is already in use.\n"
                "Close any existing Next.js instance."
            )

        # Start backend
        backend = start_backend()

        if not wait_for_service(
            f"{BACKEND_URL}/openapi.json",
            backend,
        ):
            raise RuntimeError(
                "FastAPI failed to start.\n"
                "Check the backend error messages above."
            )

        log("FastAPI backend is ready.")

        # Start frontend
        frontend = start_frontend()

        if not wait_for_service(
            FRONTEND_URL,
            frontend,
        ):
            raise RuntimeError(
                "Next.js failed to start.\n"
                "Check the frontend error messages above."
            )

        log("Next.js frontend is ready.")

        log("Opening FlightEngine...")

        webbrowser.open(FRONTEND_URL)

        log("=" * 55)
        log("FlightEngine is running successfully.")
        log(f"Frontend: {FRONTEND_URL}")
        log(f"Backend: {BACKEND_URL}")
        log("Press Ctrl+C to shut down.")
        log("=" * 55)

        while True:
            if backend.poll() is not None:
                raise RuntimeError(
                    "FastAPI stopped unexpectedly."
                )

            if frontend.poll() is not None:
                raise RuntimeError(
                    "Next.js stopped unexpectedly."
                )

            time.sleep(1)

    except KeyboardInterrupt:
        log("Shutdown requested.")

    except Exception as error:
        log(f"ERROR: {error}")

        try:
            input("\nPress Enter to close...")
        except EOFError:
            pass

    finally:
        log("Shutting down FlightEngine...")

        stop_process(frontend)
        stop_process(backend)

        log("Shutdown complete.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(
            f"[FlightEngine WIP] Fatal startup error: {error}",
            flush=True,
        )
        try:
            input("\nPress Enter to close...")
        except EOFError:
            pass
        sys.exit(1)
