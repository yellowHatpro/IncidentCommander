"""Process start-up helpers shared by the API runner and the worker."""

import logging
import socket
import sys

from api.settings import Settings

logger = logging.getLogger("incident_commander.runtime")

# How many ports above PORT `python -m api` tries before giving up.
PORT_SEARCH_WINDOW = 20


def port_is_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((host, port))
        except OSError:
            return False
    return True


def choose_port(host: str, preferred: int, *, strict: bool, window: int = PORT_SEARCH_WINDOW) -> int:
    """Return `preferred` when free, otherwise the next free port above it.

    With `strict=True` a busy preferred port raises instead of moving on.
    """
    if port_is_free(host, preferred):
        return preferred
    if strict:
        raise SystemExit(
            f"port {preferred} on {host} is already in use and PORT_STRICT=1. "
            f"Stop the other process (`lsof -nP -iTCP:{preferred} -sTCP:LISTEN`) or change PORT in .env."
        )
    for candidate in range(preferred + 1, preferred + 1 + window):
        if port_is_free(host, candidate):
            logger.warning("port %d is in use; using %d instead", preferred, candidate)
            return candidate
    raise SystemExit(
        f"no free port between {preferred} and {preferred + window} on {host}. "
        "Set PORT in .env to a free port."
    )


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def log_settings_summary(settings: Settings, component: str) -> None:
    logger.info("%s configuration:", component)
    for line in settings.summary_lines():
        logger.info("  %s", line)


def fail(message: str) -> None:
    """Print one plain error line and exit without a traceback."""
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)
