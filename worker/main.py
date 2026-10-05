import asyncio
import logging
import sqlite3

from api.gradient_client import GradientClient
from api.incident_service import process_stored_event
from api.notifier import SlackNotifier
from api.runtime import configure_logging, fail, log_settings_summary
from api.settings import get_settings
from api.store import SQLiteStore, StoreUnavailableError


logger = logging.getLogger("incident_commander.worker")


async def process_one_pending_event(store: SQLiteStore | None = None) -> bool:
    settings = get_settings()
    store = store or SQLiteStore(settings.database_path)
    client = GradientClient(settings)
    notifier = SlackNotifier(settings)
    event = store.claim_next_pending_event()
    if event is None:
        return False

    result = await process_stored_event(store, event, client, notifier)
    logger.info("processed event %s with status %s", event.id, result["status"])
    return True


async def worker_loop() -> None:
    settings = get_settings()
    configure_logging()
    log_settings_summary(settings, "worker")
    try:
        store = SQLiteStore(settings.database_path)
    except StoreUnavailableError as exc:
        fail(str(exc))
        return
    logger.info("worker started, polling every %.1fs", settings.worker_poll_interval_sec)
    while True:
        try:
            processed = await process_one_pending_event(store)
        except sqlite3.OperationalError as exc:
            # Typically "database is locked" while the API writes; retry next tick.
            logger.warning("database busy (%s); retrying in %.1fs", exc, settings.worker_poll_interval_sec)
            processed = False
        if not processed:
            # Idle: release claims left behind by a worker that died mid-analysis.
            try:
                reclaimed = store.reclaim_stale_in_progress(settings.worker_stale_after_sec)
            except sqlite3.OperationalError:
                reclaimed = 0
            if reclaimed:
                logger.warning("reclaimed %d stale in-progress event(s)", reclaimed)
            await asyncio.sleep(settings.worker_poll_interval_sec)


def main() -> None:
    try:
        asyncio.run(worker_loop())
    except KeyboardInterrupt:
        logger.info("worker stopped")


if __name__ == "__main__":
    main()
