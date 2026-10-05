"use client";

import { useState, useTransition } from "react";
import { Database, Rocket } from "lucide-react";
import { seedDemoDataAction } from "../app/actions";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";

function CodeBlock({ children }: { children: string }) {
  return (
    <pre className="overflow-x-auto rounded-xl border border-border bg-background/70 p-4 text-xs leading-6 text-foreground">
      <code>{children}</code>
    </pre>
  );
}

/**
 * First-run card: the backend answers but holds no events yet. Offers one-click
 * demo data and the curl call that real services would make.
 */
export function GettingStarted({ apiUrl, authRequired }: { apiUrl: string; authRequired: boolean }) {
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const authHeader = authRequired ? ` \\\n  -H 'X-API-Key: <INGEST_API_KEY>'` : "";

  return (
    <Card className="border-cyan-400/30">
      <CardHeader>
        <div className="flex items-center gap-2 text-cyan-300">
          <Rocket className="h-4 w-4" />
          <p className="text-xs font-semibold uppercase tracking-[0.22em]">Getting started</p>
        </div>
        <CardTitle className="text-3xl">Connected. The database is empty.</CardTitle>
        <CardDescription className="text-base">
          The API at <span className="font-mono text-foreground">{apiUrl}</span> is healthy and has not received an
          event yet. Load demo incidents to explore the console, or send a first batch of logs.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-3 text-sm leading-7 text-muted-foreground">
          <p className="font-semibold text-foreground">Option A: demo incidents</p>
          <p>
            Ingests twelve sample events from four services and analyzes them right away. No worker process is needed
            for this step.
          </p>
          <Button
            className="gap-2"
            disabled={pending}
            onClick={() =>
              startTransition(async () => {
                setError(null);
                const result = await seedDemoDataAction();
                if (!result.ok) setError(result.error);
              })
            }
          >
            <Database className="h-4 w-4" />
            {pending ? "Loading demo data…" : "Load demo incidents"}
          </Button>
          {error ? (
            <p role="alert" className="text-sm text-rose-300">
              {error}
            </p>
          ) : null}
        </div>
        <div className="space-y-3 text-sm leading-7 text-muted-foreground">
          <p className="font-semibold text-foreground">Option B: your own logs</p>
          <CodeBlock>{`curl -X POST ${apiUrl}/ingest/logs \\
  -H 'Content-Type: application/json'${authHeader} \\
  -d '{"service":"checkout","environment":"prod",
       "logs":["ERROR db connection timeout","ERROR 500 /checkout"]}'`}</CodeBlock>
          <p>
            Add <span className="font-mono">?wait_for_analysis=false</span> to queue instead, then run{" "}
            <span className="font-mono">uv run python -m worker</span> to process the queue.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
