import { PlugZap, TerminalSquare } from "lucide-react";
import type { ApiBase } from "../lib/api";
import { RetryButton } from "./retry-button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";

function CodeBlock({ children }: { children: string }) {
  return (
    <pre className="overflow-x-auto rounded-xl border border-border bg-background/70 p-4 text-xs leading-6 text-foreground">
      <code>{children}</code>
    </pre>
  );
}

const sourceLabel: Record<ApiBase["source"], string> = {
  API_BASE_URL: "the API_BASE_URL environment variable",
  NEXT_PUBLIC_API_BASE_URL: "the NEXT_PUBLIC_API_BASE_URL environment variable",
  "data/api-url": "data/api-url, written by the last `python -m api` run",
  default: "the built-in default (no API_BASE_URL set and no data/api-url file)",
};

/**
 * Shown when the backend does not answer. Explains where the frontend looked,
 * how to start the API, and how to point the frontend at another port.
 */
export function SetupPanel({ api, error }: { api: ApiBase; error: string }) {
  return (
    <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
      <Card className="border-amber-400/30">
        <CardHeader>
          <div className="flex items-center gap-2 text-amber-200">
            <PlugZap className="h-4 w-4" />
            <p className="text-xs font-semibold uppercase tracking-[0.22em]">Backend not reachable</p>
          </div>
          <CardTitle className="text-3xl">The API is not answering yet.</CardTitle>
          <CardDescription className="text-base">
            This console looked for the API at <span className="font-mono text-foreground">{api.url}</span>, taken
            from {sourceLabel[api.source]}.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5 text-sm leading-7 text-muted-foreground">
          <p className="rounded-xl border border-border bg-background/50 px-4 py-3 font-mono text-xs text-foreground">
            {error}
          </p>
          <div>
            <p className="font-semibold text-foreground">1. Start the backend from the repository root</p>
            <CodeBlock>{`cp -n .env.example .env   # optional; the defaults work as-is
uv sync
uv run python -m api       # picks the next free port if 8000 is taken`}</CodeBlock>
            <p>
              Or start API, worker and this frontend together with <span className="font-mono">./scripts/dev.sh</span>.
            </p>
          </div>
          <div>
            <p className="font-semibold text-foreground">2. Running on another port or host?</p>
            <p>
              <span className="font-mono">python -m api</span> records its URL in <span className="font-mono">data/api-url</span>{" "}
              and this console reads it automatically. For a backend started any other way, set{" "}
              <span className="font-mono">API_BASE_URL</span> in <span className="font-mono">.env</span> and restart{" "}
              <span className="font-mono">pnpm dev</span>:
            </p>
            <CodeBlock>{`API_BASE_URL=http://127.0.0.1:8001`}</CodeBlock>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <RetryButton />
            <span className="text-xs">This page also refreshes when you reload the browser.</span>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2 text-cyan-300">
            <TerminalSquare className="h-4 w-4" />
            <p className="text-xs font-semibold uppercase tracking-[0.22em]">Check from a terminal</p>
          </div>
          <CardTitle className="text-2xl">Is anything listening?</CardTitle>
          <CardDescription>Each command prints what the console needs to know.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 text-sm leading-7 text-muted-foreground">
          <div>
            <p className="text-foreground">Health check at the URL above:</p>
            <CodeBlock>{`curl ${api.url}/health`}</CodeBlock>
          </div>
          <div>
            <p className="text-foreground">What holds port 8000 right now:</p>
            <CodeBlock>{`lsof -nP -iTCP:8000 -sTCP:LISTEN`}</CodeBlock>
          </div>
          <div>
            <p className="text-foreground">The URL the last API run announced:</p>
            <CodeBlock>{`cat data/api-url`}</CodeBlock>
          </div>
          <p>
            A <span className="font-mono">.env</span> copied unchanged from <span className="font-mono">.env.example</span> is
            fine: empty or placeholder values are treated as “not configured” and the built-in analyzer is used.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
