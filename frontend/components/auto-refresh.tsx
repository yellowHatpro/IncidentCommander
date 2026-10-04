"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Pause, Play, RefreshCw } from "lucide-react";
import { Button } from "./ui/button";

/** Re-fetches the server-rendered page on an interval. Pauses when the tab is hidden. */
export function AutoRefresh({ intervalSec = 30 }: { intervalSec?: number }) {
  const router = useRouter();
  const [enabled, setEnabled] = useState(true);
  const [tick, setTick] = useState(intervalSec);

  useEffect(() => {
    if (!enabled) return;
    const timer = window.setInterval(() => {
      if (document.visibilityState !== "visible") return;
      setTick((current) => {
        if (current <= 1) {
          router.refresh();
          return intervalSec;
        }
        return current - 1;
      });
    }, 1000);
    return () => window.clearInterval(timer);
  }, [enabled, intervalSec, router]);

  return (
    <div className="inline-flex items-center gap-1 rounded-full border border-border bg-background/60 px-2 py-1 text-xs text-muted-foreground">
      <Button
        variant="ghost"
        className="h-7 px-2 py-0"
        aria-label="Refresh now"
        onClick={() => {
          router.refresh();
          setTick(intervalSec);
        }}
      >
        <RefreshCw className="h-3.5 w-3.5" />
      </Button>
      <span className="tabular-nums" aria-live="off">
        {enabled ? `auto ${tick}s` : "paused"}
      </span>
      <Button
        variant="ghost"
        className="h-7 px-2 py-0"
        aria-label={enabled ? "Pause auto refresh" : "Resume auto refresh"}
        aria-pressed={!enabled}
        onClick={() => setEnabled((value) => !value)}
      >
        {enabled ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
      </Button>
    </div>
  );
}
