import Link from "next/link";
import { ArrowRight, ShieldAlert, Sparkles, Waves } from "lucide-react";
import { DashboardShell } from "../components/dashboard-shell";
import { EmptyState } from "../components/empty-state";
import { ErrorPanel } from "../components/error-panel";
import { EventList } from "../components/event-list";
import { IncidentList } from "../components/incident-list";
import { MetricCard } from "../components/metric-card";
import { OverviewCharts } from "../components/overview-charts";
import { fetchDashboardData } from "../lib/api";
import { formatRelativeTime, formatTimestamp, severityWeight } from "../lib/format";
import { buildPressureSeries, buildSeverityChart } from "../lib/log-insights";
import { Badge } from "../components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const result = await fetchDashboardData();

  if (!result.ok) {
    return (
      <DashboardShell
        eyebrow="Next.js Operations Console"
        title="Incident visibility without the plain HTML dashboard."
        description="This frontend reads the FastAPI backend directly and turns the stored incidents and event stream into a working operator console."
      >
        <ErrorPanel message={result.error} />
      </DashboardShell>
    );
  }

  const { health, incidents, events } = result.data;
  const activeSevere = incidents.filter((incident) =>
    ["P1", "P2"].includes(incident.analysis.severity),
  );
  const pendingEvents = events.filter((event) =>
    ["analysis_pending", "analysis_in_progress"].includes(event.status),
  );
  const impactedServices = new Set(
    incidents
      .filter((incident) => severityWeight(incident.analysis.severity) <= severityWeight("P3"))
      .map((incident) => incident.service),
  );
  const latestIncident = incidents[0];
  const severityChart = buildSeverityChart(incidents);
  const pressureChart = buildPressureSeries(events);

  return (
    <DashboardShell
      eyebrow="Next.js Operations Console"
      title="Incident visibility built for triage, not just API demos."
      description="Monitor the backlog, inspect live incident summaries, and jump straight from service-level signals into detailed analysis and raw logs."
      statusLabel={health.gradient_enabled ? "Gradient live" : "Fallback analyzer"}
    >
      <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <Card className="overflow-hidden">
          <CardHeader>
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant="info">Command Brief</Badge>
              <Badge variant="outline">Env {health.environment}</Badge>
            </div>
            <CardTitle className="max-w-3xl text-4xl">
              {latestIncident
                ? latestIncident.analysis.summary
                : "No incidents detected yet."}
            </CardTitle>
            <CardDescription className="max-w-2xl text-base">
              {latestIncident
                ? `Most recent incident from ${latestIncident.service} in ${latestIncident.environment} was created ${formatRelativeTime(latestIncident.created_at)}.`
                : "Once events are ingested and analysis runs, the highest-signal incident will surface here."}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-wrap gap-3">
              {latestIncident ? (
                <Link
                  className="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground"
                  href={`/incidents/${latestIncident.id}`}
                >
                  Open incident dossier
                  <ArrowRight className="h-4 w-4" />
                </Link>
              ) : (
                <span className="inline-flex items-center rounded-full border border-border bg-background/60 px-4 py-2 text-sm text-muted-foreground">
                  Awaiting incident data
                </span>
              )}
            </div>

            <div className="grid gap-2 text-sm text-muted-foreground">
              <span className="inline-flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-cyan-300" />
                Analyzer: {health.gradient_enabled ? "Gradient" : "Fallback"}
              </span>
              <span className="inline-flex items-center gap-2">
                <Waves className="h-4 w-4 text-cyan-300" />
                Database: {health.database_path}
              </span>
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-4 sm:grid-cols-2">
          <MetricCard label="Incidents" value={incidents.length.toString()} tone="neutral" />
          <MetricCard label="P1 / P2" value={activeSevere.length.toString()} tone="critical" />
          <MetricCard
            label="Pending analysis"
            value={pendingEvents.length.toString()}
            tone="warning"
          />
          <MetricCard
            label="Services hit"
            value={impactedServices.size.toString()}
            tone="positive"
          />
        </div>
      </section>

      {incidents.length || events.length ? (
        <OverviewCharts pressureData={pressureChart} severityData={severityChart} />
      ) : null}

      <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-6">
          {incidents.length ? (
            <IncidentList incidents={incidents} />
          ) : (
            <EmptyState
              title="No incident records yet"
              description="Send warning or error logs to `/ingest/logs` and the analyzed incident timeline will appear here."
            />
          )}
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2 text-rose-300">
                <ShieldAlert className="h-4 w-4" />
                <p className="text-xs font-semibold uppercase tracking-[0.22em]">
                  Watchlist
                </p>
              </div>
              <CardTitle className="text-2xl">Where to look next</CardTitle>
              <CardDescription>
                Fast context for the operator opening this dashboard cold.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 text-sm leading-7 text-muted-foreground">
              <p>
                The queue was last updated{" "}
                {incidents.length ? formatTimestamp(incidents[0].created_at) : "recently"}.
              </p>
              <p>
                {pendingEvents.length} events are still waiting on or undergoing analysis, so the
                highest-value next click is usually the newest pending stream.
              </p>
              {events[0] ? (
                <Link
                  className="inline-flex items-center gap-2 font-medium text-cyan-300"
                  href={`/events/${events[0].id}`}
                >
                  Open latest event stream
                  <ArrowRight className="h-4 w-4" />
                </Link>
              ) : null}
            </CardContent>
          </Card>

          {events.length ? (
            <EventList events={events} />
          ) : (
            <EmptyState
              title="No event history yet"
              description="The event stream updates as services publish logs to the ingest endpoint."
            />
          )}
        </div>
      </section>
    </DashboardShell>
  );
}
