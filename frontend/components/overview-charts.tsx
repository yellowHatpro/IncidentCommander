"use client";

import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";

type ChartPoint = {
  name?: string;
  service?: string;
  value?: number;
  logs?: number;
  risk?: number;
  fill?: string;
};

export function OverviewCharts({
  severityData,
  pressureData,
}: {
  severityData: ChartPoint[];
  pressureData: ChartPoint[];
}) {
  return (
    <section className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
      <Card>
        <CardHeader>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-300">
            Severity Mix
          </p>
          <CardTitle>Where the highest pressure sits</CardTitle>
          <CardDescription>Quick read on how much of the queue is genuinely urgent.</CardDescription>
        </CardHeader>
        <CardContent className="h-[280px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={severityData}>
              <CartesianGrid stroke="rgba(148,163,184,0.12)" vertical={false} />
              <XAxis dataKey="name" stroke="rgba(148,163,184,0.5)" />
              <YAxis allowDecimals={false} stroke="rgba(148,163,184,0.5)" />
              <Tooltip cursor={{ fill: "rgba(255,255,255,0.03)" }} />
              <Bar dataKey="value" radius={[12, 12, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-300">
            Bad Stream Pressure
          </p>
          <CardTitle>Recent events by log volume and operational risk</CardTitle>
          <CardDescription>
            Combines ingestion size with processing state to highlight the streams worth opening first.
          </CardDescription>
        </CardHeader>
        <CardContent className="h-[280px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={pressureData}>
              <defs>
                <linearGradient id="risk" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="5%" stopColor="hsl(var(--chart-1))" stopOpacity={0.85} />
                  <stop offset="95%" stopColor="hsl(var(--chart-1))" stopOpacity={0.05} />
                </linearGradient>
                <linearGradient id="logs" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="5%" stopColor="hsl(var(--chart-2))" stopOpacity={0.7} />
                  <stop offset="95%" stopColor="hsl(var(--chart-2))" stopOpacity={0.05} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(148,163,184,0.12)" vertical={false} />
              <XAxis dataKey="service" stroke="rgba(148,163,184,0.5)" />
              <YAxis allowDecimals={false} stroke="rgba(148,163,184,0.5)" />
              <Tooltip cursor={{ fill: "rgba(255,255,255,0.03)" }} />
              <Area type="monotone" dataKey="risk" stroke="hsl(var(--chart-1))" fill="url(#risk)" />
              <Area type="monotone" dataKey="logs" stroke="hsl(var(--chart-2))" fill="url(#logs)" />
            </AreaChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </section>
  );
}
