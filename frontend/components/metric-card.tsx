import { Card, CardContent } from "./ui/card";

type MetricCardProps = {
  label: string;
  value: string;
  tone: "critical" | "warning" | "positive" | "neutral";
};

export function MetricCard({ label, value, tone }: MetricCardProps) {
  const toneClass = {
    critical: "text-rose-300",
    warning: "text-amber-200",
    positive: "text-emerald-200",
    neutral: "text-cyan-200",
  }[tone];

  return (
    <Card className="min-h-[150px]">
      <CardContent className="p-6">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">
          {label}
        </p>
        <div className={`mt-4 text-4xl font-semibold sm:text-5xl ${toneClass}`}>{value}</div>
      </CardContent>
    </Card>
  );
}
