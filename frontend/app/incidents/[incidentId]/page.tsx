import Link from "next/link";
import { ArrowRight, FileDown, Link2, Megaphone, Siren, Sparkles } from "lucide-react";
import { DashboardShell } from "../../../components/dashboard-shell";
import { ErrorPanel } from "../../../components/error-panel";
import { IncidentActions } from "../../../components/incident-actions";
import { IncidentNotes } from "../../../components/incident-notes";
import { StatusBadge } from "../../../components/status-badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../../components/ui/card";
import { fetchIncidentDetail, postmortemUrl } from "../../../lib/api";
import { formatRelativeTime, formatTimestamp } from "../../../lib/format";

export const dynamic = "force-dynamic";

export default async function IncidentDetailPage({
  params,
}: {
  params: Promise<{ incidentId: string }>;
}) {
  const { incidentId } = await params;
  const result = await fetchIncidentDetail(incidentId);

  if (!result.ok) {
    return (
      <DashboardShell
        eyebrow="Incident Dossier"
        title="Unable to load incident detail."
        description="The incident API call failed. Verify that the backend is running and the incident ID exists."
      >
        <ErrorPanel message={result.error} />
      </DashboardShell>
    );
  }

  const { incident, event } = result.data;

  return (
    <DashboardShell
      eyebrow="Incident Dossier"
      title={incident.analysis.summary}
      description={`Detailed analysis for ${incident.service} in ${incident.environment}.`}
      statusLabel={incident.status}
      toolbar={
        <a
          className="inline-flex items-center gap-2 rounded-full border border-border bg-background/60 px-4 py-2 text-sm font-semibold text-foreground hover:bg-accent"
          href={postmortemUrl(incident.id)}
          download
        >
          <FileDown className="h-4 w-4" />
          Postmortem .md
        </a>
      }
    >
      <section className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2 text-rose-300">
              <Siren className="h-4 w-4" />
              <p className="text-xs font-semibold uppercase tracking-[0.22em]">Severity</p>
            </div>
            <CardTitle>Escalation context</CardTitle>
            <CardDescription>Core incident metadata for the current investigation.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-3">
              <StatusBadge variant="severity" value={incident.analysis.severity} />
              <StatusBadge variant="incident" value={incident.status} />
              <StatusBadge variant="status" value={event.status} />
            </div>
            <div className="space-y-2 text-sm text-muted-foreground">
              <p>Created {formatTimestamp(incident.created_at)}</p>
              {incident.resolved_at ? (
                <p>
                  Resolved {formatTimestamp(incident.resolved_at)} (
                  {Math.max(1, Math.round((new Date(incident.resolved_at).getTime() - new Date(incident.created_at).getTime()) / 60000))}{" "}
                  min)
                </p>
              ) : (
                <p>Open for {formatRelativeTime(incident.created_at).replace(/ ago$/, "")}</p>
              )}
              <p>Source: {incident.analysis.source}</p>
              <p>Event ID: {incident.event_id}</p>
            </div>
            <IncidentActions incidentId={incident.id} status={incident.status} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2 text-cyan-300">
              <Sparkles className="h-4 w-4" />
              <p className="text-xs font-semibold uppercase tracking-[0.22em]">Scope</p>
            </div>
            <CardTitle>Service and environment</CardTitle>
            <CardDescription>Where the incident is happening and where to pivot next.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-2 text-sm text-muted-foreground">
            <p>Service: {incident.service}</p>
            <p>Environment: {incident.environment}</p>
            <Link className="inline-flex w-fit items-center gap-2 pt-2 font-medium text-cyan-300" href={`/events/${incident.event_id}`}>
              Open related event
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              className="inline-flex w-fit items-center gap-2 font-medium text-cyan-300"
              href={`/?service=${encodeURIComponent(incident.service)}&environment=${encodeURIComponent(incident.environment)}`}
            >
              All incidents for this service
              <ArrowRight className="h-4 w-4" />
            </Link>
          </CardContent>
        </Card>
      </section>

      {incident.related_incidents.length ? (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2 text-amber-200">
              <Link2 className="h-4 w-4" />
              <p className="text-xs font-semibold uppercase tracking-[0.22em]">Correlation</p>
            </div>
            <CardTitle>Related incidents (same service, ±24h)</CardTitle>
            <CardDescription>Repeat signals may share a root cause; check before opening a new investigation.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-2">
            {incident.related_incidents.map((related) => (
              <Link
                key={related.id}
                href={`/incidents/${related.id}`}
                className="rounded-2xl border border-border/60 bg-white/[0.03] p-4 transition-colors hover:border-cyan-300/40"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <StatusBadge variant="severity" value={related.analysis.severity} />
                  <StatusBadge variant="incident" value={related.status} />
                  <span className="text-xs text-muted-foreground">{formatRelativeTime(related.created_at)}</span>
                </div>
                <p className="mt-2 text-sm text-foreground">{related.analysis.summary}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {related.analysis.hypotheses[0]?.cause ?? "No hypothesis"}
                </p>
              </Link>
            ))}
          </CardContent>
        </Card>
      ) : null}

      <section className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>User impact</CardTitle>
            <CardDescription>Who is affected and how that impact shows up.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {incident.analysis.user_impact.map((item) => (
              <div className="rounded-2xl border border-border/60 bg-white/[0.03] p-4" key={item}>
                <p className="text-sm leading-7 text-muted-foreground">{item}</p>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Suggested actions</CardTitle>
            <CardDescription>Recommended next steps for triage and mitigation.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {incident.analysis.suggested_actions.map((item) => (
              <div className="rounded-2xl border border-border/60 bg-white/[0.03] p-4" key={item}>
                <p className="text-sm leading-7 text-muted-foreground">{item}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Likely causes</CardTitle>
            <CardDescription>Confidence-ranked hypotheses from the analyzer.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {incident.analysis.hypotheses.map((item) => (
              <div
                className="grid gap-3 rounded-2xl border border-border/60 bg-white/[0.03] p-4 sm:grid-cols-[auto_1fr]"
                key={`${item.rank}-${item.cause}`}
              >
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-cyan-400/10 font-semibold text-cyan-200">
                  #{item.rank}
                </div>
                <div>
                  <p className="font-medium text-foreground">{item.cause}</p>
                  <p className="mt-1 text-sm text-muted-foreground">Confidence {(item.confidence * 100).toFixed(0)}%</p>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2 text-cyan-300">
              <Megaphone className="h-4 w-4" />
              <p className="text-xs font-semibold uppercase tracking-[0.22em]">Comms</p>
            </div>
            <CardTitle>Slack update</CardTitle>
            <CardDescription>Incident-ready wording for immediate stakeholder communication.</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="rounded-2xl border border-border/60 bg-white/[0.03] p-4 text-sm leading-7 text-muted-foreground">
              {incident.analysis.slack_update}
            </p>
          </CardContent>
        </Card>
      </section>

      <IncidentNotes incidentId={incident.id} notes={incident.notes} />

      <section className="grid gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Initial postmortem draft</CardTitle>
            <CardDescription>
              Structured draft text that can seed follow-up documentation. Use the download button for the full
              Markdown document with timeline and evidence.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="rounded-2xl border border-border/60 bg-white/[0.03] p-4 text-sm leading-7 text-muted-foreground">
              {incident.analysis.postmortem_draft}
            </p>
          </CardContent>
        </Card>
      </section>
    </DashboardShell>
  );
}
