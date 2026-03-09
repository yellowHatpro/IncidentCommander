import Link from "next/link";
import type { EventSummary } from "../lib/types";
import { formatRelativeTime, formatTimestamp } from "../lib/format";
import { StatusBadge } from "./status-badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";

export function EventList({ events }: { events: EventSummary[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent event intake</CardTitle>
        <CardDescription>Includes pending and completed analysis states.</CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Status</TableHead>
              <TableHead>Service</TableHead>
              <TableHead>Signal</TableHead>
              <TableHead>Logs</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {events.map((event) => (
              <TableRow key={event.id}>
                <TableCell className="space-y-2">
                  <StatusBadge variant="status" value={event.status} />
                  {event.incident_severity ? (
                    <StatusBadge variant="severity" value={event.incident_severity} />
                  ) : null}
                </TableCell>
                <TableCell>
                  <Link className="font-medium text-foreground hover:text-cyan-300" href={`/events/${event.id}`}>
                    {event.service}
                  </Link>
                  <div className="mt-1 text-xs uppercase tracking-[0.18em] text-muted-foreground">
                    {event.environment}
                  </div>
                </TableCell>
                <TableCell>
                  <div className="font-medium text-foreground">
                    {event.incident_summary ?? event.signal_preview}
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {formatRelativeTime(event.timestamp)} · {formatTimestamp(event.timestamp)}
                  </div>
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">{event.log_count}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
