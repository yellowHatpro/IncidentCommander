import Link from "next/link";
import { ArrowRight, DatabaseZap, Radar } from "lucide-react";
import { DashboardShell } from "../../../components/dashboard-shell";
import { ErrorPanel } from "../../../components/error-panel";
import { LogStreamPanel } from "../../../components/log-stream-panel";
import { StatusBadge } from "../../../components/status-badge";
import { Badge } from "../../../components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../../components/ui/card";
import { fetchEventDetail } from "../../../lib/api";
import { formatTimestamp } from "../../../lib/format";
import { summarizeEventLogStream, summarizeKeywords } from "../../../lib/log-insights";

export const dynamic = "force-dynamic";

export default async function EventDetailPage({
  params,
}: {
  params: Promise<{ eventId: string }>;
}) {
  const { eventId } = await params;
  const result = await fetchEventDetail(eventId);

  if (!result.ok) {
    return (
      <DashboardShell
        eyebrow="Event Trace"
        title="Unable to load event detail."
        description="The event API call failed. Verify that the backend is running and the event ID exists."
      >
        <ErrorPanel message={result.error} />
      </DashboardShell>
    );
  }

  const { event } = result.data;
  const severityData = summarizeEventLogStream(event);
  const keywordData = summarizeKeywords(event);

  return (
    <DashboardShell
      eyebrow="Event Trace"
      title={`${event.service} signal intake`}
      description={`Raw logs and analysis state for the ${event.environment} event record.`}
    >
      <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2 text-cyan-300">
              <Radar className="h-4 w-4" />
              <p className="text-xs font-semibold uppercase tracking-[0.22em]">
                Event Status
              </p>
            </div>
            <CardTitle>Processing state and attached incident context</CardTitle>
            <CardDescription>
              Primary operator metadata for deciding whether to escalate or inspect logs.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-3">
              <StatusBadge variant="status" value={event.status} />
              {event.incident_severity ? (
                <StatusBadge variant="severity" value={event.incident_severity} />
              ) : null}
            </div>
            <div className="grid gap-2 text-sm text-muted-foreground">
              <p>Captured {formatTimestamp(event.timestamp)}</p>
              <p>Event ID: {event.id}</p>
              <p>Service: {event.service}</p>
              <p>Environment: {event.environment}</p>
            </div>
            {event.incident_id ? (
              <Link
                className="inline-flex items-center gap-2 font-medium text-cyan-300"
                href={`/incidents/${event.incident_id}`}
              >
                Open related incident
                <ArrowRight className="h-4 w-4" />
              </Link>
            ) : (
              <Badge variant="outline">No incident attached yet</Badge>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2 text-cyan-300">
              <DatabaseZap className="h-4 w-4" />
              <p className="text-xs font-semibold uppercase tracking-[0.22em]">
                Analyst Summary
              </p>
            </div>
            <CardTitle>What this stream suggests</CardTitle>
            <CardDescription>
              A compact summary before dropping into the individual log lines.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm leading-7 text-muted-foreground">
            {event.incident_summary ? <p>{event.incident_summary}</p> : <p>No incident summary is attached to this event yet.</p>}
            {event.last_error ? (
              <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-rose-100">
                {event.last_error}
              </div>
            ) : null}
          </CardContent>
        </Card>
      </section>

      <LogStreamPanel event={event} keywordData={keywordData} severityData={severityData} />

      {event.incident_summary ? (
        <section className="grid gap-6">
          <Card>
            <CardHeader>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-300">
                Attached Analysis
              </p>
              <CardTitle>Incident summary</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm leading-7 text-muted-foreground">{event.incident_summary}</p>
            </CardContent>
          </Card>
        </section>
      ) : null}
    </DashboardShell>
  );
}
