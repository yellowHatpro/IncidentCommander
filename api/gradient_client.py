import json

import httpx
from pydantic import ValidationError

from api.models import IncidentAnalysis
from api.settings import Settings


class GradientClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def analyze(self, service: str, environment: str, logs: list[str]) -> IncidentAnalysis:
        if not self.settings.gradient_enabled:
            return self._fallback_analysis(service, environment, logs)

        try:
            payload = {
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "Return valid JSON only with these exact keys: "
                            "severity, summary, user_impact, hypotheses, suggested_actions, "
                            "slack_update, postmortem_draft.\n"
                            f"Service: {service}\n"
                            f"Environment: {environment}\n"
                            "Logs:\n"
                            + "\n".join(logs)
                        ),
                    }
                ],
                "stream": False,
            }

            async with httpx.AsyncClient(timeout=self.settings.request_timeout_sec) as client:
                response = await client.post(
                    f"{self.settings.agent_endpoint.rstrip('/')}/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.settings.agent_access_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            parsed["source"] = "gradient"
            return IncidentAnalysis.model_validate(parsed)
        except (httpx.HTTPError, KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError):
            return self._fallback_analysis(service, environment, logs)

    def _fallback_analysis(self, service: str, environment: str, logs: list[str]) -> IncidentAnalysis:
        joined = "\n".join(logs).lower()
        error_count = sum("error" in line.lower() for line in logs)
        timeout_signal = any(token in joined for token in ["timeout", "timed out", "latency"])
        db_signal = any(token in joined for token in ["db", "database", "postgres", "mysql"])
        deploy_signal = any(token in joined for token in ["deploy", "release", "rollback"])

        if error_count >= 3 or ("500" in joined and timeout_signal):
            severity = "P1"
        elif error_count >= 2 or "critical" in joined:
            severity = "P2"
        elif error_count >= 1 or "warn" in joined:
            severity = "P3"
        else:
            severity = "P4"

        if db_signal:
            cause = "Database connectivity or saturation issue"
            confidence = 0.84
        elif deploy_signal:
            cause = "Recent deploy introduced a regression"
            confidence = 0.73
        elif timeout_signal:
            cause = "Latency spike or upstream timeout"
            confidence = 0.69
        else:
            cause = "Application-level fault requiring triage"
            confidence = 0.58

        return IncidentAnalysis.model_validate(
            {
                "severity": severity,
                "summary": f"{service} is showing repeated error signals in {environment}.",
                "user_impact": ["User-facing requests may fail or degrade."],
                "hypotheses": [
                    {
                        "rank": 1,
                        "cause": cause,
                        "confidence": confidence,
                    }
                ],
                "suggested_actions": [
                    "Inspect recent deploys and infrastructure health.",
                    "Check error rate, latency, and saturation dashboards.",
                ],
                "slack_update": (
                    f"Incident detected in {service} ({environment}): severity {severity}. "
                    f"Investigating likely {cause.lower()}."
                ),
                "postmortem_draft": (
                    f"Summary: {service} experienced elevated {environment} errors. "
                    "Next steps: validate infra health, correlate with deployments, and mitigate the suspected bottleneck."
                ),
                "source": "fallback",
            }
        )
