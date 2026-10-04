import asyncio
import logging

from api.gradient_client import GradientClient
from api.incident_service import process_stored_event
from api.notifier import SlackNotifier
from api.settings import get_settings
from api.store import SQLiteStore


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
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    store = SQLiteStore(settings.database_path)
    logger.info("worker started, polling %s every %.1fs", settings.database_path, settings.worker_poll_interval_sec)
    while True:
        processed = await process_one_pending_event(store)
        if not processed:
            # Idle: release claims left behind by a worker that died mid-analysis.
            reclaimed = store.reclaim_stale_in_progress(settings.worker_stale_after_sec)
            if reclaimed:
                logger.warning("reclaimed %d stale in-progress event(s)", reclaimed)
            await asyncio.sleep(settings.worker_poll_interval_sec)


def main() -> None:
    asyncio.run(worker_loop())


if __name__ == "__main__":
    main()
