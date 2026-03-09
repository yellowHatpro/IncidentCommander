import asyncio
import logging

from api.gradient_client import GradientClient
from api.incident_service import process_stored_event
from api.notifier import SlackNotifier
from api.settings import get_settings
from api.store import SQLiteStore


logger = logging.getLogger("incident_commander.worker")


async def process_one_pending_event() -> bool:
    settings = get_settings()
    store = SQLiteStore(settings.database_path)
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
    while True:
        processed = await process_one_pending_event()
        if not processed:
            await asyncio.sleep(settings.worker_poll_interval_sec)


def main() -> None:
    asyncio.run(worker_loop())


if __name__ == "__main__":
    main()

