from typing import Any

from api.gradient_client import GradientClient
from api.models import StoredEvent
from api.notifier import SlackNotifier
from api.store import SQLiteStore


async def process_stored_event(
    store: SQLiteStore,
    event: StoredEvent,
    client: GradientClient,
    notifier: SlackNotifier,
) -> dict[str, Any]:
    try:
        analysis = await client.analyze(event.service, event.environment, event.logs)
        incident = store.add_incident(event, analysis)
        store.update_event_status(event.id, "analysis_complete")
        await notifier.send_incident_update(incident)
        return {
            "status": "analysis_complete",
            "incident_id": incident.id,
            "analysis": analysis,
        }
    except Exception as exc:
        store.update_event_status(event.id, "analysis_failed", str(exc))
        return {
            "status": "analysis_failed",
            "incident_id": None,
            "analysis": None,
        }

