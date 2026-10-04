"use client";

import { useRef, useState, useTransition } from "react";
import { MessageSquarePlus } from "lucide-react";
import { addIncidentNoteAction } from "../app/actions";
import type { IncidentNote } from "../lib/types";
import { formatTimestamp } from "../lib/format";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";

export function IncidentNotes({ incidentId, notes }: { incidentId: string; notes: IncidentNote[] }) {
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const formRef = useRef<HTMLFormElement>(null);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2 text-cyan-300">
          <MessageSquarePlus className="h-4 w-4" />
          <p className="text-xs font-semibold uppercase tracking-[0.22em]">Timeline</p>
        </div>
        <CardTitle>Operator notes</CardTitle>
        <CardDescription>What was tried, when, and by whom. Notes feed the postmortem export.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {notes.length ? (
          <ol className="space-y-3">
            {notes.map((note) => (
              <li key={note.id} className="rounded-2xl border border-border/60 bg-white/[0.03] p-4">
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">
                  <span>{note.author}</span>
                  <time dateTime={note.created_at}>{formatTimestamp(note.created_at)}</time>
                </div>
                <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-foreground">{note.text}</p>
              </li>
            ))}
          </ol>
        ) : (
          <p className="text-sm text-muted-foreground">No notes yet. Record the first action taken.</p>
        )}

        <form
          ref={formRef}
          className="grid gap-3 rounded-2xl border border-dashed border-border/60 p-4"
          action={(formData) =>
            startTransition(async () => {
              setError(null);
              const result = await addIncidentNoteAction(incidentId, formData);
              if (!result.ok) {
                setError(result.error);
                return;
              }
              formRef.current?.reset();
            })
          }
        >
          <div className="grid gap-3 sm:grid-cols-[160px_1fr]">
            <label className="grid gap-1 text-xs uppercase tracking-[0.18em] text-muted-foreground">
              Author
              <input
                name="author"
                maxLength={80}
                placeholder="operator"
                className="rounded-xl border border-input bg-background/60 px-3 py-2 text-sm normal-case tracking-normal text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </label>
            <label className="grid gap-1 text-xs uppercase tracking-[0.18em] text-muted-foreground">
              Note
              <textarea
                name="text"
                required
                maxLength={4000}
                rows={2}
                placeholder="Rolled back deploy 2026.10.04-3; error rate recovering."
                className="rounded-xl border border-input bg-background/60 px-3 py-2 text-sm normal-case tracking-normal text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </label>
          </div>
          <div className="flex items-center justify-between gap-3">
            {error ? (
              <p role="alert" className="text-sm text-rose-300">
                {error}
              </p>
            ) : (
              <span />
            )}
            <Button type="submit" variant="outline" disabled={pending}>
              {pending ? "Saving…" : "Add note"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
