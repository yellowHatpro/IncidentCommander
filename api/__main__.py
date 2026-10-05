"""`python -m api` starts the API on PORT, or the next free port when PORT is busy.

The chosen URL is printed and written to data/api-url so the Next.js frontend
(and scripts) can find the backend without editing .env.
"""

import argparse
import logging
import os
import signal

import uvicorn

from api.runtime import choose_port, configure_logging, fail, log_settings_summary
from api.settings import PROJECT_ROOT, get_settings
from api.store import SQLiteStore, StoreUnavailableError

logger = logging.getLogger("incident_commander.api")

API_URL_FILE = PROJECT_ROOT / "data" / "api-url"


def write_api_url(url: str) -> None:
    try:
        API_URL_FILE.parent.mkdir(parents=True, exist_ok=True)
        API_URL_FILE.write_text(url + "\n", encoding="utf-8")
    except OSError as exc:  # the API still works; only discovery is lost
        logger.warning("could not write %s (%s); set API_BASE_URL for the frontend", API_URL_FILE, exc)


def clear_api_url() -> None:
    try:
        API_URL_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def _exit_on_signal(signum: int, _frame: object) -> None:
    # uvicorn re-raises the signal it caught once shutdown completes, so the
    # `finally` in main() would not run. Clear the discovery file here instead.
    clear_api_url()
    raise SystemExit(0)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m api", description="Run the Incident Commander API.")
    parser.add_argument("--host", help="bind address (default: HOST from .env, else 127.0.0.1)")
    parser.add_argument("--port", type=int, help="preferred port (default: PORT from .env, else 8000)")
    parser.add_argument("--strict-port", action="store_true", help="fail instead of moving to a free port")
    parser.add_argument("--reload", action="store_true", help="restart on code changes (development)")
    args = parser.parse_args(argv)

    configure_logging()
    settings = get_settings()
    host = args.host or settings.host
    preferred = args.port or settings.port

    try:
        SQLiteStore(settings.database_path)
    except StoreUnavailableError as exc:
        fail(str(exc))

    port = choose_port(host, preferred, strict=args.strict_port or settings.port_strict)
    url = f"http://{host}:{port}"
    log_settings_summary(settings, "API")
    if port != preferred:
        logger.warning("PORT=%d was busy. Frontend: set API_BASE_URL=%s or let it read data/api-url.", preferred, url)
    logger.info("API      : %s", url)
    logger.info("docs     : %s/docs", url)
    logger.info("dashboard: %s/dashboard", url)

    write_api_url(url)
    signal.signal(signal.SIGTERM, _exit_on_signal)
    signal.signal(signal.SIGINT, _exit_on_signal)
    # The app lifespan prints the same summary; skip it when this runner already did.
    os.environ["INCIDENT_COMMANDER_SUMMARY_PRINTED"] = "1"
    try:
        uvicorn.run(
            "api.main:app",
            host=host,
            port=port,
            reload=args.reload,
            # Only our own code; node_modules and data/ would trigger restarts otherwise.
            reload_dirs=[str(PROJECT_ROOT / "api"), str(PROJECT_ROOT / "worker")] if args.reload else None,
            log_level="info",
        )
    finally:
        clear_api_url()


if __name__ == "__main__":
    main()
