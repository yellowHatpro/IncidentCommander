"use client";

import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { MetricsSummary } from "../lib/types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";

const severityStroke: Record<"P1" | "P2" | "P3" | "P4", string> = {
  P1: "hsl(var(--chart-5))",
  P2: "hsl(var(--chart-1))",
  P3: "hsl(var(--chart-3))",
  P4: "hsl(var(--chart-4))",
};

function hourLabel(iso: string) {
  return new Intl.DateTimeFormat("en-US", { hour: "2-digit", hour12: false, timeZone: "UTC" }).format(new Date(iso)) + "h";
}

export function IncidentTrend({ metrics }: { metrics: MetricsSummary }) {
  const data = metrics.incidents_per_hour.map((point) => ({ ...point, label: hourLabel(point.bucket) }));
  const mttr = metrics.mean_time_to_resolve_sec;

  return (
    <Card>
      <CardHeader>
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-300">
          Last {metrics.window_hours}h (UTC)
        </p>
        <CardTitle>Incidents per hour by severity</CardTitle>
        <CardDescription>
          {metrics.resolved_count} resolved
          {mttr !== null ? ` · mean time to resolve ${(mttr / 60).toFixed(0)} min` : " · no resolutions yet"}
          {" · "}
          {metrics.incidents_by_status.open} open, {metrics.incidents_by_status.acknowledged} acknowledged
        </CardDescription>
      </CardHeader>
      <CardContent className="h-[280px]">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data}>
            <defs>
              <linearGradient id="trend-total" x1="0" x2="0" y1="0" y2="1">
                <stop offset="5%" stopColor="hsl(var(--chart-2))" stopOpacity={0.45} />
                <stop offset="95%" stopColor="hsl(var(--chart-2))" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="rgba(148,163,184,0.12)" vertical={false} />
            <XAxis dataKey="label" stroke="rgba(148,163,184,0.5)" interval="preserveStartEnd" />
            <YAxis allowDecimals={false} stroke="rgba(148,163,184,0.5)" />
            <Tooltip
              cursor={{ stroke: "rgba(255,255,255,0.1)" }}
              contentStyle={{ background: "hsl(225 40% 11%)", border: "1px solid hsl(217 25% 22%)", borderRadius: 12 }}
            />
            <Legend />
            <Area
              type="monotone"
              dataKey="total"
              name="All"
              stroke="hsl(var(--chart-2))"
              fill="url(#trend-total)"
              isAnimationActive={false}
            />
            {(["P1", "P2", "P3", "P4"] as const).map((severity) => (
              <Line
                key={severity}
                type="monotone"
                dataKey={severity}
                stroke={severityStroke[severity]}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
