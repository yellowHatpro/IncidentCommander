import httpx

from api.models import StoredIncident
from api.settings import Settings


class SlackNotifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send_incident_update(self, incident: StoredIncident) -> bool:
        if not self.settings.slack_webhook_url:
            return False

        payload = {
            "text": incident.analysis.slack_update,
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*{incident.service}* in *{incident.environment}*\n"
                            f"Severity: `{incident.analysis.severity}`\n"
                            f"{incident.analysis.summary}"
                        ),
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Suggested actions:*\n- "
                        + "\n- ".join(incident.analysis.suggested_actions),
                    },
                },
            ],
        }

        async with httpx.AsyncClient(timeout=self.settings.request_timeout_sec) as client:
            response = await client.post(self.settings.slack_webhook_url, json=payload)
            response.raise_for_status()
        return True

