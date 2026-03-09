import type { EventDetail, EventSummary, StoredIncident } from "./types";

export type LogTone = "critical" | "error" | "warning" | "info";

type KeywordBucket = {
  label: string;
  score: number;
};

const keywordMap = [
  { label: "Database", patterns: ["db", "database", "sql", "connection", "pool"] },
  { label: "Timeouts", patterns: ["timeout", "timed out", "latency", "deadline"] },
  { label: "Auth", patterns: ["auth", "token", "login", "credential", "permission"] },
  { label: "Checkout", patterns: ["checkout", "payment", "order", "cart"] },
  { label: "Queue", patterns: ["queue", "worker", "job", "retry"] },
  { label: "Deploy", patterns: ["deploy", "release", "rollback", "migration"] },
  { label: "Inventory", patterns: ["inventory", "reservation", "stock"] },
];

export function detectLogTone(message: string): LogTone {
  const value = message.toLowerCase();
  if (value.includes("critical") || value.includes("panic") || value.includes("fatal")) {
    return "critical";
  }
  if (value.includes("error") || value.includes("500") || value.includes("failed")) {
    return "error";
  }
  if (value.includes("warn") || value.includes("retry") || value.includes("degraded")) {
    return "warning";
  }
  return "info";
}

export function summarizeEventLogStream(event: EventDetail) {
  const totals = {
    critical: 0,
    error: 0,
    warning: 0,
    info: 0,
  };

  for (const entry of event.log_entries) {
    totals[detectLogTone(entry.message)] += 1;
  }

  const total = event.log_entries.length || 1;
  return [
    { name: "Critical", value: totals.critical, fill: "hsl(var(--chart-5))" },
    { name: "Error", value: totals.error, fill: "hsl(var(--chart-1))" },
    { name: "Warning", value: totals.warning, fill: "hsl(var(--chart-3))" },
    { name: "Info", value: totals.info, fill: "hsl(var(--chart-2))" },
  ].map((item) => ({
    ...item,
    percentage: Math.round((item.value / total) * 100),
  }));
}

export function summarizeKeywords(event: EventDetail): KeywordBucket[] {
  const buckets = keywordMap.map((bucket) => ({ label: bucket.label, score: 0 }));

  for (const entry of event.log_entries) {
    const message = entry.message.toLowerCase();
    keywordMap.forEach((bucket, index) => {
      if (bucket.patterns.some((pattern) => message.includes(pattern))) {
        buckets[index].score += 1;
      }
    });
  }

  return buckets.filter((bucket) => bucket.score > 0).sort((a, b) => b.score - a.score).slice(0, 5);
}

export function buildSeverityChart(incidents: StoredIncident[]) {
  const counts = { P1: 0, P2: 0, P3: 0, P4: 0 };
  for (const incident of incidents) {
    counts[incident.analysis.severity] += 1;
  }
  return [
    { name: "P1", value: counts.P1, fill: "hsl(var(--chart-5))" },
    { name: "P2", value: counts.P2, fill: "hsl(var(--chart-1))" },
    { name: "P3", value: counts.P3, fill: "hsl(var(--chart-3))" },
    { name: "P4", value: counts.P4, fill: "hsl(var(--chart-2))" },
  ];
}

export function buildPressureSeries(events: EventSummary[]) {
  return [...events]
    .slice(0, 8)
    .reverse()
    .map((event) => ({
      service: event.service.replace(/-service|-api/g, ""),
      logs: event.log_count,
      risk:
        event.status === "analysis_failed"
          ? 95
          : event.status === "analysis_pending"
            ? 82
            : event.status === "analysis_in_progress"
              ? 68
              : event.status === "analysis_complete"
                ? 48
                : 18,
    }));
}
