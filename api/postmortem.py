"""Render an incident as a Markdown postmortem document."""

from api.models import StoredEvent, StoredIncident


def _fmt(value) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S UTC") if value else "n/a"


def render_postmortem_markdown(incident: StoredIncident, event: StoredEvent | None) -> str:
    analysis = incident.analysis
    duration = ""
    if incident.resolved_at:
        minutes = (incident.resolved_at - incident.created_at).total_seconds() / 60
        duration = f"{minutes:.0f} min"

    lines: list[str] = [
        f"# Postmortem: {incident.service} ({incident.environment})",
        "",
        f"- **Incident ID:** `{incident.id}`",
        f"- **Severity:** {analysis.severity}",
        f"- **Status:** {incident.status}",
        f"- **Detected:** {_fmt(incident.created_at)}",
        f"- **Resolved:** {_fmt(incident.resolved_at)}" + (f" (duration {duration})" if duration else ""),
        f"- **Analysis source:** {analysis.source}",
        "",
        "## Summary",
        "",
        analysis.summary,
        "",
        "## User impact",
        "",
        *(f"- {item}" for item in analysis.user_impact or ["No impact recorded."]),
        "",
        "## Root cause hypotheses",
        "",
        *(
            [f"{h.rank}. {h.cause} (confidence {h.confidence:.0%})" for h in analysis.hypotheses]
            or ["No hypotheses were generated."]
        ),
        "",
        "## Suggested actions",
        "",
        *(f"- [ ] {item}" for item in analysis.suggested_actions or ["No actions suggested."]),
        "",
        "## Timeline",
        "",
        f"- {_fmt(event.timestamp) if event else _fmt(incident.created_at)}: signals received",
        f"- {_fmt(incident.created_at)}: incident opened",
    ]
    for note in incident.notes:
        lines.append(f"- {_fmt(note.created_at)}: {note.author}: {note.text}")
    if incident.resolved_at:
        lines.append(f"- {_fmt(incident.resolved_at)}: incident resolved")
    lines += [
        "",
        "## Draft narrative",
        "",
        analysis.postmortem_draft,
        "",
        "## Stakeholder update",
        "",
        f"> {analysis.slack_update}",
        "",
        "## Evidence",
        "",
        "```text",
        *(event.logs if event else ["Linked event not found."]),
        "```",
        "",
    ]
    return "\n".join(lines)
