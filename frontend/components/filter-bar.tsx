import Link from "next/link";
import { Filter, X } from "lucide-react";
import type { IncidentFilters, IncidentStatus, Severity } from "../lib/types";
import { Button } from "./ui/button";

const severities: Severity[] = ["P1", "P2", "P3", "P4"];
const statuses: IncidentStatus[] = ["open", "acknowledged", "resolved"];

const selectClass =
  "rounded-xl border border-input bg-background/60 px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

/** Plain GET form: works without client JavaScript and keeps filters in the URL. */
export function FilterBar({
  filters,
  services,
  environments,
  total,
}: {
  filters: IncidentFilters;
  services: string[];
  environments: string[];
  total: number;
}) {
  const active = Object.values(filters).filter(Boolean).length;

  return (
    <form
      method="get"
      action="/"
      className="flex flex-wrap items-end gap-3 rounded-3xl border border-border/70 bg-card/60 p-4"
      aria-label="Filter incidents"
    >
      <div className="flex items-center gap-2 pb-2 text-xs font-semibold uppercase tracking-[0.22em] text-cyan-300">
        <Filter className="h-4 w-4" />
        Filters
      </div>

      <label className="grid gap-1 text-xs uppercase tracking-[0.18em] text-muted-foreground">
        Service
        <select name="service" defaultValue={filters.service ?? ""} className={selectClass}>
          <option value="">All</option>
          {services.map((service) => (
            <option key={service} value={service}>
              {service}
            </option>
          ))}
        </select>
      </label>

      <label className="grid gap-1 text-xs uppercase tracking-[0.18em] text-muted-foreground">
        Environment
        <select name="environment" defaultValue={filters.environment ?? ""} className={selectClass}>
          <option value="">All</option>
          {environments.map((environment) => (
            <option key={environment} value={environment}>
              {environment}
            </option>
          ))}
        </select>
      </label>

      <label className="grid gap-1 text-xs uppercase tracking-[0.18em] text-muted-foreground">
        Severity
        <select name="severity" defaultValue={filters.severity ?? ""} className={selectClass}>
          <option value="">All</option>
          {severities.map((severity) => (
            <option key={severity} value={severity}>
              {severity}
            </option>
          ))}
        </select>
      </label>

      <label className="grid gap-1 text-xs uppercase tracking-[0.18em] text-muted-foreground">
        Status
        <select name="status" defaultValue={filters.status ?? ""} className={selectClass}>
          <option value="">All</option>
          {statuses.map((status) => (
            <option key={status} value={status}>
              {status}
            </option>
          ))}
        </select>
      </label>

      <div className="flex items-center gap-2">
        <Button type="submit" variant="outline">
          Apply
        </Button>
        {active ? (
          <Link
            href="/"
            className="inline-flex items-center gap-1 rounded-full px-3 py-2 text-sm text-muted-foreground hover:text-foreground"
          >
            <X className="h-3.5 w-3.5" />
            Clear
          </Link>
        ) : null}
      </div>

      <p className="ml-auto pb-2 text-sm text-muted-foreground">
        {total} incident{total === 1 ? "" : "s"} match
      </p>
    </form>
  );
}
