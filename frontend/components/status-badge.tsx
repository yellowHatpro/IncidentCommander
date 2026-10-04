import { Badge } from "./ui/badge";

type StatusBadgeProps = {
  variant: "severity" | "status" | "incident";
  value: string;
};

function pickVariant(variant: StatusBadgeProps["variant"], value: string) {
  const normalized = value.toLowerCase();
  if (variant === "severity") {
    if (value === "P1" || value === "P2") return "danger";
    return value === "P3" ? "warning" : "success";
  }
  if (variant === "incident") {
    if (normalized === "open") return "danger";
    return normalized === "acknowledged" ? "warning" : "success";
  }
  if (normalized.includes("failed")) return "danger";
  if (normalized.includes("pending")) return "warning";
  if (normalized.includes("progress")) return "info";
  if (normalized === "ignored") return "outline";
  return "success";
}

export function StatusBadge({ variant, value }: StatusBadgeProps) {
  return <Badge variant={pickVariant(variant, value)}>{value.replaceAll("_", " ")}</Badge>;
}
