from html import escape

from api.models import StoredEvent, StoredIncident


def _truncate(value: str, limit: int = 140) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "..."


def _severity_badge(severity: str) -> str:
    return f'<span class="badge severity severity-{escape(severity.lower())}">{escape(severity)}</span>'


def _status_badge(status: str) -> str:
    css = status.replace("_", "-")
    label = status.replace("_", " ")
    return f'<span class="badge status status-{escape(css)}">{escape(label)}</span>'


def _page_shell(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      --bg: #efe8dc;
      --paper: #fbf6ee;
      --ink: #1f2937;
      --muted: #6b7280;
      --line: #d8ccba;
      --accent: #0f766e;
      --accent-soft: rgba(15, 118, 110, 0.1);
      --shadow: rgba(55, 36, 18, 0.08);
      --p1: #b91c1c;
      --p2: #c2410c;
      --p3: #a16207;
      --p4: #166534;
      --pending: #9a3412;
      --progress: #0f766e;
      --complete: #166534;
      --failed: #b91c1c;
      --ignored: #6b7280;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif;
      background:
        radial-gradient(circle at top right, rgba(15, 118, 110, 0.18), transparent 24%),
        radial-gradient(circle at bottom left, rgba(194, 65, 12, 0.15), transparent 28%),
        linear-gradient(180deg, #f4ede2 0%, var(--bg) 100%);
    }}
    a {{
      color: inherit;
      text-decoration: none;
    }}
    .wrap {{
      max-width: 1320px;
      margin: 0 auto;
      padding: 28px 18px 40px;
    }}
    .hero {{
      background: linear-gradient(135deg, rgba(251, 246, 238, 0.98), rgba(245, 238, 227, 0.92));
      border: 1px solid var(--line);
      box-shadow: 0 18px 60px var(--shadow);
      padding: 26px 28px;
      position: relative;
      overflow: hidden;
    }}
    .hero::after {{
      content: "";
      position: absolute;
      inset: 0;
      background:
        linear-gradient(90deg, transparent 0%, rgba(15, 118, 110, 0.08) 48%, transparent 100%);
      pointer-events: none;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(2rem, 3vw, 3.2rem);
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }}
    .sub {{
      margin-top: 10px;
      color: var(--muted);
      max-width: 820px;
      font-size: 1rem;
    }}
    .topline {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      align-items: center;
      margin-top: 18px;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.72);
      padding: 8px 12px;
      font-size: 0.86rem;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }}
    .grid {{
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 20px;
      margin-top: 20px;
      align-items: start;
    }}
    .stack {{
      display: grid;
      gap: 16px;
    }}
    .panel {{
      background: rgba(251, 246, 238, 0.96);
      border: 1px solid var(--line);
      box-shadow: 0 16px 46px var(--shadow);
      overflow: hidden;
    }}
    .panel-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 16px 18px;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.42);
    }}
    .panel-title {{
      margin: 0;
      font-size: 1.4rem;
    }}
    .panel-meta {{
      color: var(--muted);
      font-size: 0.84rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 12px;
      padding: 18px;
    }}
    .metric {{
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.5);
      padding: 14px;
    }}
    .metric-label {{
      color: var(--muted);
      font-size: 0.75rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .metric-value {{
      margin-top: 8px;
      font-size: 1.7rem;
      line-height: 1;
    }}
    .timeline {{
      padding: 14px 18px 20px;
      display: grid;
      gap: 12px;
    }}
    .entry {{
      display: grid;
      grid-template-columns: 150px 1fr;
      gap: 14px;
      padding: 16px;
      border: 1px solid var(--line);
      background: linear-gradient(135deg, rgba(255,255,255,0.58), rgba(247,240,227,0.72));
      transition: transform 120ms ease, box-shadow 120ms ease, border-color 120ms ease;
    }}
    .entry:hover {{
      transform: translateY(-1px);
      box-shadow: 0 10px 28px rgba(55, 36, 18, 0.08);
      border-color: rgba(15, 118, 110, 0.35);
    }}
    .entry-time {{
      color: var(--muted);
      font-size: 0.82rem;
      line-height: 1.4;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .entry-main {{
      min-width: 0;
    }}
    .entry-top {{
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .entry-service {{
      font-size: 1.1rem;
      font-weight: 700;
    }}
    .entry-summary {{
      margin-top: 8px;
      font-size: 0.95rem;
      color: #374151;
    }}
    .entry-preview {{
      margin-top: 10px;
      padding-top: 10px;
      border-top: 1px dashed var(--line);
      color: var(--muted);
      font-size: 0.88rem;
      display: grid;
      gap: 4px;
    }}
    .entry-link {{
      margin-top: 10px;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--accent);
      font-size: 0.88rem;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 4px 9px;
      font-size: 0.74rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: #fff;
    }}
    .severity-p1 {{ background: var(--p1); }}
    .severity-p2 {{ background: var(--p2); }}
    .severity-p3 {{ background: var(--p3); }}
    .severity-p4 {{ background: var(--p4); }}
    .status-analysis-pending {{ background: var(--pending); }}
    .status-analysis-in-progress {{ background: var(--progress); }}
    .status-analysis-complete {{ background: var(--complete); }}
    .status-analysis-failed {{ background: var(--failed); }}
    .status-ignored {{ background: var(--ignored); }}
    .detail {{
      margin-top: 20px;
      display: grid;
      gap: 18px;
    }}
    .detail-card {{
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.48);
      padding: 18px;
    }}
    .detail-title {{
      margin: 0 0 12px;
      font-size: 1rem;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: var(--muted);
    }}
    .kv {{
      display: grid;
      gap: 10px;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    }}
    .kv-item {{
      border-top: 1px solid var(--line);
      padding-top: 10px;
    }}
    .kv-label {{
      font-size: 0.72rem;
      color: var(--muted);
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .kv-value {{
      margin-top: 6px;
      font-size: 1rem;
      word-break: break-word;
    }}
    ul.clean {{
      margin: 0;
      padding-left: 18px;
      display: grid;
      gap: 8px;
    }}
    pre {{
      margin: 0;
      padding: 14px;
      border: 1px solid var(--line);
      background: rgba(33, 37, 41, 0.94);
      color: #f9fafb;
      overflow: auto;
      font: 0.86rem/1.5 "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
    }}
    .breadcrumbs {{
      display: inline-flex;
      gap: 10px;
      align-items: center;
      color: var(--muted);
      font-size: 0.88rem;
      text-transform: uppercase;
      letter-spacing: 0.07em;
    }}
    .empty {{
      padding: 18px;
      color: var(--muted);
    }}
    @media (max-width: 980px) {{
      .grid {{ grid-template-columns: 1fr; }}
      .entry {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    {body}
  </div>
</body>
</html>
"""


def render_dashboard(incidents: list[StoredIncident], events: list[StoredEvent]) -> str:
    p1_count = sum(1 for incident in incidents if incident.analysis.severity == "P1")
    pending_count = sum(1 for event in events if event.status == "analysis_pending")
    latest_incident = incidents[0].created_at.isoformat() if incidents else "No incidents"
    latest_event = events[0].timestamp.isoformat() if events else "No events"

    incident_entries = "".join(
        f"""
        <a class="entry" href="/dashboard/incidents/{escape(incident.id)}">
          <div class="entry-time">
            <div>{escape(incident.created_at.strftime("%Y-%m-%d"))}</div>
            <div>{escape(incident.created_at.strftime("%H:%M:%S UTC"))}</div>
          </div>
          <div class="entry-main">
            <div class="entry-top">
              <span class="entry-service">{escape(incident.service)}</span>
              <span class="pill">{escape(incident.environment)}</span>
              {_severity_badge(incident.analysis.severity)}
            </div>
            <div class="entry-summary">{escape(incident.analysis.summary)}</div>
            <div class="entry-preview">
              <div><strong>Likely cause:</strong> {escape(incident.analysis.hypotheses[0].cause if incident.analysis.hypotheses else "Unknown")}</div>
              <div><strong>User impact:</strong> {escape(_truncate(" | ".join(incident.analysis.user_impact), 110))}</div>
            </div>
            <span class="entry-link">Open incident detail -></span>
          </div>
        </a>
        """
        for incident in incidents
    )

    event_entries = "".join(
        f"""
        <a class="entry" href="/dashboard/events/{escape(event.id)}">
          <div class="entry-time">
            <div>{escape(event.timestamp.strftime("%Y-%m-%d"))}</div>
            <div>{escape(event.timestamp.strftime("%H:%M:%S UTC"))}</div>
          </div>
          <div class="entry-main">
            <div class="entry-top">
              <span class="entry-service">{escape(event.service)}</span>
              <span class="pill">{escape(event.environment)}</span>
              {_status_badge(event.status)}
            </div>
            <div class="entry-summary">{escape(_truncate(event.logs[0], 180))}</div>
            <div class="entry-preview">
              {''.join(f'<div>{escape(_truncate(log, 120))}</div>' for log in event.logs[:3])}
            </div>
            <span class="entry-link">Open event detail -></span>
          </div>
        </a>
        """
        for event in events
    )

    if not incident_entries:
        incident_entries = '<div class="empty">No incidents analyzed yet.</div>'
    if not event_entries:
        event_entries = '<div class="empty">No events received yet.</div>'

    body = f"""
    <section class="hero">
      <h1>Incident Commander</h1>
      <div class="sub">A control-room view for recent incidents and operational signals. Entries are ordered by time and every row drills into the underlying evidence.</div>
      <div class="topline">
        <span class="pill">Latest incident: {escape(latest_incident)}</span>
        <span class="pill">Latest event: {escape(latest_event)}</span>
        <span class="pill">Dashboard links: incidents, events, detail pages</span>
      </div>
    </section>
    <section class="grid">
      <div class="stack">
        <section class="panel">
          <div class="panel-head">
            <h2 class="panel-title">Incident Timeline</h2>
            <div class="panel-meta">{len(incidents)} recent incidents</div>
          </div>
          <div class="timeline">{incident_entries}</div>
        </section>
      </div>
      <div class="stack">
        <section class="panel">
          <div class="panel-head">
            <h2 class="panel-title">Operational Snapshot</h2>
            <div class="panel-meta">Current state</div>
          </div>
          <div class="metric-grid">
            <div class="metric">
              <div class="metric-label">Recent Incidents</div>
              <div class="metric-value">{len(incidents)}</div>
            </div>
            <div class="metric">
              <div class="metric-label">Recent Events</div>
              <div class="metric-value">{len(events)}</div>
            </div>
            <div class="metric">
              <div class="metric-label">P1 Count</div>
              <div class="metric-value">{p1_count}</div>
            </div>
            <div class="metric">
              <div class="metric-label">Pending Events</div>
              <div class="metric-value">{pending_count}</div>
            </div>
          </div>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2 class="panel-title">Signal Stream</h2>
            <div class="panel-meta">{len(events)} recent events</div>
          </div>
          <div class="timeline">{event_entries}</div>
        </section>
      </div>
    </section>
    """
    return _page_shell("Incident Commander Dashboard", body)


def render_incident_detail(incident: StoredIncident, event: StoredEvent | None) -> str:
    hypotheses = "".join(
        f"<li>#{hypothesis.rank}: {escape(hypothesis.cause)} (confidence {hypothesis.confidence:.2f})</li>"
        for hypothesis in incident.analysis.hypotheses
    ) or "<li>No hypotheses were generated.</li>"
    actions = "".join(f"<li>{escape(action)}</li>" for action in incident.analysis.suggested_actions) or "<li>No actions suggested.</li>"
    impacts = "".join(f"<li>{escape(item)}</li>" for item in incident.analysis.user_impact) or "<li>No impact recorded.</li>"
    logs = "\n".join(event.logs) if event else "Linked event not found."

    body = f"""
    <div class="breadcrumbs"><a href="/dashboard">Dashboard</a> / Incident / {escape(incident.id)}</div>
    <section class="hero">
      <h1>{escape(incident.service)} Incident</h1>
      <div class="sub">{escape(incident.analysis.summary)}</div>
      <div class="topline">
        {_severity_badge(incident.analysis.severity)}
        <span class="pill">{escape(incident.environment)}</span>
        <span class="pill">Created {escape(incident.created_at.isoformat())}</span>
        <span class="pill">Source {escape(incident.analysis.source)}</span>
      </div>
    </section>
    <section class="detail">
      <div class="detail-card">
        <h2 class="detail-title">Summary</h2>
        <div class="kv">
          <div class="kv-item"><div class="kv-label">Incident ID</div><div class="kv-value">{escape(incident.id)}</div></div>
          <div class="kv-item"><div class="kv-label">Event ID</div><div class="kv-value"><a href="/dashboard/events/{escape(incident.event_id)}">{escape(incident.event_id)}</a></div></div>
          <div class="kv-item"><div class="kv-label">Service</div><div class="kv-value">{escape(incident.service)}</div></div>
          <div class="kv-item"><div class="kv-label">Environment</div><div class="kv-value">{escape(incident.environment)}</div></div>
        </div>
      </div>
      <div class="detail-card">
        <h2 class="detail-title">User Impact</h2>
        <ul class="clean">{impacts}</ul>
      </div>
      <div class="detail-card">
        <h2 class="detail-title">Root Cause Hypotheses</h2>
        <ul class="clean">{hypotheses}</ul>
      </div>
      <div class="detail-card">
        <h2 class="detail-title">Suggested Actions</h2>
        <ul class="clean">{actions}</ul>
      </div>
      <div class="detail-card">
        <h2 class="detail-title">Slack Update</h2>
        <pre>{escape(incident.analysis.slack_update)}</pre>
      </div>
      <div class="detail-card">
        <h2 class="detail-title">Postmortem Draft</h2>
        <pre>{escape(incident.analysis.postmortem_draft)}</pre>
      </div>
      <div class="detail-card">
        <h2 class="detail-title">Linked Event Logs</h2>
        <pre>{escape(logs)}</pre>
      </div>
    </section>
    """
    return _page_shell(f"{incident.service} Incident", body)


def render_event_detail(event: StoredEvent, incident: StoredIncident | None) -> str:
    incident_link = (
        f'<a href="/dashboard/incidents/{escape(incident.id)}">{escape(incident.id)}</a>'
        if incident
        else "No incident created yet."
    )
    incident_summary = escape(incident.analysis.summary) if incident else "No incident summary available."
    rendered_logs = "\n".join(f"[{event.timestamp.isoformat()}] {log}" for log in event.logs)
    body = f"""
    <div class="breadcrumbs"><a href="/dashboard">Dashboard</a> / Event / {escape(event.id)}</div>
    <section class="hero">
      <h1>{escape(event.service)} Event</h1>
      <div class="sub">Raw operational signal batch with processing state and linked incident context.</div>
      <div class="topline">
        {_status_badge(event.status)}
        <span class="pill">{escape(event.environment)}</span>
        <span class="pill">Timestamp {escape(event.timestamp.isoformat())}</span>
      </div>
    </section>
    <section class="detail">
      <div class="detail-card">
        <h2 class="detail-title">Event Summary</h2>
        <div class="kv">
          <div class="kv-item"><div class="kv-label">Event ID</div><div class="kv-value">{escape(event.id)}</div></div>
          <div class="kv-item"><div class="kv-label">Service</div><div class="kv-value">{escape(event.service)}</div></div>
          <div class="kv-item"><div class="kv-label">Environment</div><div class="kv-value">{escape(event.environment)}</div></div>
          <div class="kv-item"><div class="kv-label">Incident</div><div class="kv-value">{incident_link}</div></div>
        </div>
      </div>
      <div class="detail-card">
        <h2 class="detail-title">Raw Logs</h2>
        <pre>{escape(rendered_logs)}</pre>
      </div>
      <div class="detail-card">
        <h2 class="detail-title">Processing</h2>
        <div class="kv">
          <div class="kv-item"><div class="kv-label">Status</div><div class="kv-value">{escape(event.status)}</div></div>
          <div class="kv-item"><div class="kv-label">Last Error</div><div class="kv-value">{escape(event.last_error or "None")}</div></div>
          <div class="kv-item"><div class="kv-label">Incident Severity</div><div class="kv-value">{escape(incident.analysis.severity if incident else "None")}</div></div>
          <div class="kv-item"><div class="kv-label">Incident Summary</div><div class="kv-value">{incident_summary}</div></div>
        </div>
      </div>
    </section>
    """
    return _page_shell(f"{event.service} Event", body)
