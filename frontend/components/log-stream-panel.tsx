"use client";

import { AlertTriangle, Bug, Info, Siren, Timer } from "lucide-react";
import { Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { EventDetail } from "../lib/types";
import { detectLogTone } from "../lib/log-insights";
import { formatTimestamp } from "../lib/format";
import { Badge } from "./ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Progress } from "./ui/progress";
import { ScrollArea } from "./ui/scroll-area";

const toneIcon = {
  critical: Siren,
  error: Bug,
  warning: AlertTriangle,
  info: Info,
};

const toneClasses = {
  critical: "border-rose-500/40 bg-rose-500/10",
  error: "border-red-400/30 bg-red-400/10",
  warning: "border-amber-400/30 bg-amber-400/10",
  info: "border-sky-400/30 bg-sky-400/10",
};

export function LogStreamPanel({
  event,
  severityData,
  keywordData,
}: {
  event: EventDetail;
  severityData: Array<{ name: string; value: number; percentage: number; fill: string }>;
  keywordData: Array<{ label: string; score: number }>;
}) {
  const highestBucket = severityData[0]?.percentage ?? 0;

  return (
    <section className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
      <div className="grid gap-6">
        <Card>
          <CardHeader>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-300">
              Stream Health
            </p>
            <CardTitle>Bad log signal composition</CardTitle>
            <CardDescription>
              Visual split of the event stream by detected log tone.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-6 lg:grid-cols-[220px_1fr]">
            <div className="h-[220px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={severityData}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={58}
                    outerRadius={88}
                    paddingAngle={4}
                  >
                    {severityData.map((entry) => (
                      <Cell fill={entry.fill} key={entry.name} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>

            <div className="space-y-4">
              {severityData.map((entry) => (
                <div key={entry.name} className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium text-foreground">{entry.name}</span>
                    <span className="text-muted-foreground">
                      {entry.value} lines · {entry.percentage}%
                    </span>
                  </div>
                  <Progress value={entry.percentage} />
                </div>
              ))}
              <div className="rounded-2xl border border-border/60 bg-white/[0.03] p-4 text-sm text-muted-foreground">
                Highest concentration: <span className="text-foreground">{highestBucket}%</span> of
                the stream is clustered in a single severity band.
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-300">
              Trigger Hotspots
            </p>
            <CardTitle>What the logs are pointing at</CardTitle>
            <CardDescription>Keyword clustering highlights likely failure domains.</CardDescription>
          </CardHeader>
          <CardContent className="h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={keywordData} layout="vertical" margin={{ left: 12, right: 12 }}>
                <CartesianGrid stroke="rgba(148,163,184,0.12)" horizontal={false} />
                <XAxis type="number" allowDecimals={false} stroke="rgba(148,163,184,0.5)" />
                <YAxis
                  dataKey="label"
                  type="category"
                  width={88}
                  stroke="rgba(148,163,184,0.5)"
                />
                <Tooltip cursor={{ fill: "rgba(255,255,255,0.03)" }} />
                <Bar dataKey="score" radius={[0, 12, 12, 0]} fill="hsl(var(--chart-2))" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-300">
            Log Stream
          </p>
          <CardTitle>Readable event timeline</CardTitle>
          <CardDescription>
            Severity-coded cards make it easier to scan repeated failure signatures.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ScrollArea>
            <div className="space-y-4">
              {event.log_entries.map((entry, index) => {
                const tone = detectLogTone(entry.message);
                const Icon = toneIcon[tone];
                return (
                  <div
                    className={`rounded-2xl border p-4 ${toneClasses[tone]}`}
                    key={`${entry.timestamp}-${index}`}
                  >
                    <div className="mb-3 flex items-center justify-between gap-4">
                      <div className="flex items-center gap-3">
                        <div className="rounded-full border border-white/10 bg-background/60 p-2">
                          <Icon className="h-4 w-4 text-foreground" />
                        </div>
                        <Badge variant={tone === "critical" || tone === "error" ? "danger" : tone === "warning" ? "warning" : "info"}>
                          {tone}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">
                        <Timer className="h-3.5 w-3.5" />
                        {formatTimestamp(entry.timestamp)}
                      </div>
                    </div>
                    <p className="font-mono text-sm leading-6 text-slate-100">{entry.message}</p>
                  </div>
                );
              })}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>
    </section>
  );
}
