import Link from "next/link";
import type { StoredIncident } from "../lib/types";
import { formatRelativeTime, formatTimestamp } from "../lib/format";
import { StatusBadge } from "./status-badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";

export function IncidentList({ incidents, total }: { incidents: StoredIncident[]; total?: number }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Incident queue</CardTitle>
        <CardDescription>
          Newest first.
          {total !== undefined && total > incidents.length
            ? ` Showing ${incidents.length} of ${total}; narrow with the filters above.`
            : ""}
        </CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Severity</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Service</TableHead>
              <TableHead>Summary</TableHead>
              <TableHead>Opened</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {incidents.map((incident) => (
              <TableRow key={incident.id}>
                <TableCell>
                  <StatusBadge variant="severity" value={incident.analysis.severity} />
                </TableCell>
                <TableCell>
                  <StatusBadge variant="incident" value={incident.status} />
                  {incident.notes.length ? (
                    <div className="mt-1 text-xs text-muted-foreground">
                      {incident.notes.length} note{incident.notes.length === 1 ? "" : "s"}
                    </div>
                  ) : null}
                </TableCell>
                <TableCell>
                  <Link className="font-medium text-foreground hover:text-cyan-300" href={`/incidents/${incident.id}`}>
                    {incident.service}
                  </Link>
                  <div className="mt-1 text-xs uppercase tracking-[0.18em] text-muted-foreground">
                    {incident.environment} · {incident.analysis.source}
                  </div>
                </TableCell>
                <TableCell>
                  <div className="font-medium text-foreground">{incident.analysis.summary}</div>
                  <div className="mt-1 text-sm text-muted-foreground">
                    {incident.analysis.hypotheses[0]?.cause ?? "No cause hypothesis returned."}
                  </div>
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  <div>{formatRelativeTime(incident.created_at)}</div>
                  <div className="mt-1 text-xs">{formatTimestamp(incident.created_at)}</div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
