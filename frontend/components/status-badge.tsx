import { Badge } from "./ui/badge";

type StatusBadgeProps = {
  variant: "severity" | "status";
  value: string;
};

export function StatusBadge({ variant, value }: StatusBadgeProps) {
  const normalized = value.toLowerCase();
  const badgeVariant =
    variant === "severity"
      ? value === "P1" || value === "P2"
        ? "danger"
        : value === "P3"
          ? "warning"
          : "success"
      : normalized.includes("failed")
        ? "danger"
        : normalized.includes("pending")
          ? "warning"
          : normalized.includes("progress")
            ? "info"
            : "success";

  return <Badge variant={badgeVariant}>{value.replaceAll("_", " ")}</Badge>;
}
