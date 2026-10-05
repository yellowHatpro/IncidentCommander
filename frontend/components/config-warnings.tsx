import { AlertTriangle } from "lucide-react";
import { Card, CardContent } from "./ui/card";

/** Compact amber notice for configuration the backend found set but unusable. */
export function ConfigWarnings({ warnings }: { warnings: string[] }) {
  if (!warnings.length) return null;
  return (
    <Card className="border-amber-400/30">
      <CardContent className="flex flex-col gap-2 py-4 text-sm leading-6 text-muted-foreground sm:flex-row sm:items-start sm:gap-4">
        <div className="flex shrink-0 items-center gap-2 text-amber-200">
          <AlertTriangle className="h-4 w-4" />
          <span className="text-xs font-semibold uppercase tracking-[0.22em]">Configuration</span>
        </div>
        <ul className="space-y-1">
          {warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
          <li className="text-xs">
            Edit <span className="font-mono">.env</span> at the repository root and restart the API to clear these.
          </li>
        </ul>
      </CardContent>
    </Card>
  );
}
