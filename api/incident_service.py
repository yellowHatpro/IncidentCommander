import logging
from typing import Any

from api.gradient_client import GradientClient
from api.models import StoredEvent
from api.notifier import SlackNotifier
from api.store import SQLiteStore

logger = logging.getLogger("incident_commander.service")


async def process_stored_event(
    store: SQLiteStore,
    event: StoredEvent,
    client: GradientClient,
    notifier: SlackNotifier,
) -> dict[str, Any]:
    """Analyze an event, persist the incident, then notify.

    Notification is best-effort: a Slack failure is logged and recorded on the
    event but never undoes a completed analysis.
    """
    try:
        analysis = await client.analyze(event.service, event.environment, event.logs)
        incident = store.add_incident(event, analysis)
    except Exception as exc:
        logger.exception("analysis failed for event %s", event.id)
        store.update_event_status(event.id, "analysis_failed", str(exc))
        return {
            "status": "analysis_failed",
            "incident_id": None,
            "analysis": None,
        }

    notify_error: str | None = None
    try:
        await notifier.send_incident_update(incident)
    except Exception as exc:
        notify_error = f"notification failed: {exc}"
        logger.warning("slack notification failed for incident %s: %s", incident.id, exc)

    store.update_event_status(event.id, "analysis_complete", notify_error)
    return {
        "status": "analysis_complete",
        "incident_id": incident.id,
        "analysis": analysis,
    }
