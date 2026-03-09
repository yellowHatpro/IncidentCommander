import type { ReactNode } from "react";
import Link from "next/link";
import { Activity, ArrowUpRight } from "lucide-react";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card } from "./ui/card";

type DashboardShellProps = {
  eyebrow: string;
  title: string;
  description: string;
  statusLabel?: string;
  children: ReactNode;
};

export function DashboardShell({
  eyebrow,
  title,
  description,
  statusLabel,
  children,
}: DashboardShellProps) {
  return (
    <main className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <Card className="mb-6 overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.16),transparent_28%),radial-gradient(circle_at_bottom_right,rgba(244,63,94,0.12),transparent_24%)]" />
        <header className="relative flex flex-col gap-6 p-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-300">
              {eyebrow}
            </p>
            <h1 className="mt-3 max-w-4xl font-serif text-4xl leading-none sm:text-5xl lg:text-6xl">
              {title}
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-muted-foreground sm:text-base">
              {description}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {statusLabel ? (
              <Badge className="gap-2 rounded-full px-4 py-2" variant="info">
                <Activity className="h-3.5 w-3.5" />
                {statusLabel}
              </Badge>
            ) : null}
            <Link href="/">
              <Button className="gap-2">
                Overview
                <ArrowUpRight className="h-4 w-4" />
              </Button>
            </Link>
          </div>
        </header>
      </Card>

      <div className="space-y-6">
        <div className="hidden" />
        <div>
          <p className="sr-only">Dashboard content</p>
        </div>
        {children}
      </div>
    </main>
  );
}
