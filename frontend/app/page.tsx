import Link from "next/link";
import { ArrowRight, ShieldAlert, Sparkles, Waves } from "lucide-react";
import { AutoRefresh } from "../components/auto-refresh";
import { ConfigWarnings } from "../components/config-warnings";
import { DashboardShell } from "../components/dashboard-shell";
import { EmptyState } from "../components/empty-state";
import { ErrorPanel } from "../components/error-panel";
import { GettingStarted } from "../components/getting-started";
import { SetupPanel } from "../components/setup-panel";
import { EventList } from "../components/event-list";
import { FilterBar } from "../components/filter-bar";
import { IncidentList } from "../components/incident-list";
import { IncidentTrend } from "../components/incident-trend";
import { MetricCard } from "../components/metric-card";
import { OverviewCharts } from "../components/overview-charts";
import { describeApiBase, fetchDashboardData } from "../lib/api";
import { formatRelativeTime, formatTimestamp } from "../lib/format";
import { buildPressureSeries, buildSeverityChart } from "../lib/log-insights";
import type { IncidentFilters, IncidentStatus, Severity } from "../lib/types";
import { Badge } from "../components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";

export const dynamic = "force-dynamic";

type SearchParams = Record<string, string | string[] | undefined>;

const severities = new Set<string>(["P1", "P2", "P3", "P4"]);
const statuses = new Set<string>(["open", "acknowledged", "resolved"]);

function first(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

function parseFilters(params: SearchParams): IncidentFilters {
  const severity = first(params.severity);
  const status = first(params.status);
  return {
    service: first(params.service) || undefined,
    environment: first(params.environment) || undefined,
    severity: severity && severities.has(severity) ? (severity as Severity) : undefined,
    status: status && statuses.has(status) ? (status as IncidentStatus) : undefined,
  };
}

export default async function HomePage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const filters = parseFilters(await searchParams);
  const result = await fetchDashboardData(filters);

  if (!result.ok) {
    return (
      <DashboardShell
        eyebrow="Next.js Operations Console"
        title={result.unreachable ? "Let's connect this console to the API." : "Incident visibility without the plain HTML dashboard."}
        description={
          result.unreachable
            ? "The frontend is running. It needs the FastAPI backend to answer before it can show incidents."
            : "This frontend reads the FastAPI backend directly and turns the stored incidents and event stream into a working operator console."
        }
      >
        {result.unreachable ? <SetupPanel api={result.api} error={result.error} /> : <ErrorPanel message={result.error} />}
      </DashboardShell>
    );
  }

  const { health, incidents, incidentsTotal, events, eventsTotal, metrics } = result.data;
  const filtersActive = Object.values(filters).some(Boolean);
  const firstRun = health.events_total === 0 && eventsTotal === 0 && !filtersActive;
  const databaseName = health.database_path.split(/[\\/]/).pop() ?? health.database_path;
  const openSevere = incidents.filter(
    (incident) => incident.status !== "resolved" && ["P1", "P2"].includes(incident.analysis.severity),
  );
  const pendingEvents = health.queue_depth + health.in_progress;
  const latestIncident = incidents.find((incident) => incident.status !== "resolved") ?? incidents[0];
  const severityChart = buildSeverityChart(incidents);
  const pressureChart = buildPressureSeries(events);
  const services = Array.from(new Set(metrics.top_services.map((item) => item.service))).sort();
  const environments = Array.from(new Set(metrics.top_services.map((item) => item.environment))).sort();

  return (
    <DashboardShell
      eyebrow="Next.js Operations Console"
      title="Incident visibility built for triage, not just API demos."
      description="Monitor the backlog, inspect live incident summaries, and jump straight from service-level signals into detailed analysis and raw logs."
      statusLabel={health.gradient_enabled ? "Gradient live" : "Fallback analyzer"}
      toolbar={<AutoRefresh intervalSec={30} />}
    >
      <ConfigWarnings warnings={health.config_warnings} />

      {firstRun ? <GettingStarted apiUrl={describeApiBase().url} authRequired={health.ingest_auth_enabled} /> : null}

      <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <Card className="overflow-hidden">
          <CardHeader>
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant="info">Command Brief</Badge>
              <Badge variant="outline">Env {health.environment}</Badge>
              {!health.database_ok ? <Badge variant="danger">Database unreachable</Badge> : null}
            </div>
            <CardTitle className="max-w-3xl text-4xl">
              {latestIncident ? latestIncident.analysis.summary : "No incidents detected yet."}
            </CardTitle>
            <CardDescription className="max-w-2xl text-base">
              {latestIncident
                ? `Most recent ${latestIncident.status} incident from ${latestIncident.service} in ${latestIncident.environment} was created ${formatRelativeTime(latestIncident.created_at)}.`
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
              <span className="inline-flex items-center gap-2" title={health.analyzer_reason ?? undefined}>
                <Sparkles className="h-4 w-4 text-cyan-300" />
                Analyzer: {health.gradient_enabled ? "Gradient" : "Fallback (built-in)"}
                {health.slack_enabled ? " · Slack on" : ""}
                {health.ingest_auth_enabled ? " · API key required" : ""}
              </span>
              <span className="inline-flex items-center gap-2" title={health.database_path}>
                <Waves className="h-4 w-4 text-cyan-300" />
                Database: {databaseName} · API v{health.version}
              </span>
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-4 sm:grid-cols-2">
          <MetricCard label="Open incidents" value={metrics.incidents_by_status.open.toString()} tone="neutral" />
          <MetricCard label="Open P1 / P2" value={openSevere.length.toString()} tone="critical" />
          <MetricCard label="Queue depth" value={pendingEvents.toString()} tone="warning" />
          <MetricCard label="Resolved" value={metrics.incidents_by_status.resolved.toString()} tone="positive" />
        </div>
      </section>

      <FilterBar filters={filters} services={services} environments={environments} total={incidentsTotal} />

      {metrics.incidents_total ? <IncidentTrend metrics={metrics} /> : null}

      {incidents.length || events.length ? (
        <OverviewCharts pressureData={pressureChart} severityData={severityChart} />
      ) : null}

      <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-6">
          {incidents.length ? (
            <IncidentList incidents={incidents} total={incidentsTotal} />
          ) : (
            <EmptyState
              title={filtersActive ? "No incidents match these filters" : "No incident records yet"}
              description="Send warning or error logs to `/ingest/logs` (or an Alertmanager webhook to `/ingest/alertmanager`) and the analyzed incident timeline will appear here."
            />
          )}
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2 text-rose-300">
                <ShieldAlert className="h-4 w-4" />
                <p className="text-xs font-semibold uppercase tracking-[0.22em]">Watchlist</p>
              </div>
              <CardTitle className="text-2xl">Where to look next</CardTitle>
              <CardDescription>Fast context for the operator opening this dashboard cold.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 text-sm leading-7 text-muted-foreground">
              <p>
                The queue was last updated {incidents.length ? formatTimestamp(incidents[0].created_at) : "recently"}.
              </p>
              <p>
                {pendingEvents} event{pendingEvents === 1 ? " is" : "s are"} still waiting on or undergoing analysis,
                so the highest-value next click is usually the newest pending stream.
              </p>
              {metrics.top_services.length ? (
                <ul className="space-y-1">
                  {metrics.top_services.slice(0, 3).map((item) => (
                    <li key={`${item.service}-${item.environment}`} className="flex justify-between gap-3">
                      <Link className="text-cyan-300" href={`/?service=${encodeURIComponent(item.service)}`}>
                        {item.service}
                        <span className="text-muted-foreground"> · {item.environment}</span>
                      </Link>
                      <span>{item.count}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
              {events[0] ? (
                <Link className="inline-flex items-center gap-2 font-medium text-cyan-300" href={`/events/${events[0].id}`}>
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
