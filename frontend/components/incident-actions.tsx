"use client";

import { useState, useTransition } from "react";
import { CheckCircle2, Eye, RotateCcw } from "lucide-react";
import { setIncidentStatusAction } from "../app/actions";
import type { IncidentStatus } from "../lib/types";
import { Button } from "./ui/button";

const transitions: Record<IncidentStatus, Array<{ to: IncidentStatus; label: string; icon: typeof Eye }>> = {
  open: [
    { to: "acknowledged", label: "Acknowledge", icon: Eye },
    { to: "resolved", label: "Resolve", icon: CheckCircle2 },
  ],
  acknowledged: [
    { to: "resolved", label: "Resolve", icon: CheckCircle2 },
    { to: "open", label: "Reopen", icon: RotateCcw },
  ],
  resolved: [{ to: "open", label: "Reopen", icon: RotateCcw }],
};

export function IncidentActions({
  incidentId,
  status,
}: {
  incidentId: string;
  status: IncidentStatus;
}) {
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        {transitions[status].map(({ to, label, icon: Icon }) => (
          <Button
            key={to}
            variant={to === "resolved" ? "default" : "outline"}
            disabled={pending}
            aria-label={`${label} incident`}
            onClick={() =>
              startTransition(async () => {
                setError(null);
                const result = await setIncidentStatusAction(incidentId, to);
                if (!result.ok) setError(result.error);
              })
            }
            className="gap-2"
          >
            <Icon className="h-4 w-4" />
            {pending ? "Saving…" : label}
          </Button>
        ))}
      </div>
      {error ? (
        <p role="alert" className="text-sm text-rose-300">
          {error}
        </p>
      ) : null}
    </div>
  );
}
