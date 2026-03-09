import type { Severity } from "./types";

export function formatTimestamp(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function formatRelativeTime(value: string) {
  const timestamp = new Date(value).getTime();
  const deltaMs = timestamp - Date.now();
  const minutes = Math.round(deltaMs / 60000);
  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

  if (Math.abs(minutes) < 60) {
    return rtf.format(minutes, "minute");
  }

  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 48) {
    return rtf.format(hours, "hour");
  }

  const days = Math.round(hours / 24);
  return rtf.format(days, "day");
}

export function severityWeight(severity: Severity) {
  const weights: Record<Severity, number> = {
    P1: 1,
    P2: 2,
    P3: 3,
    P4: 4,
  };
  return weights[severity];
}
