"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, MessageSquarePlus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import type { Note } from "@/lib/domain";
import { formatDate } from "@/lib/format";
import { describeError } from "@/lib/intake";

/** One choice in the "About" picker: an application at its current stage. */
export interface NoteContext {
  value: string;
  label: string;
  applicationId: number;
  stageKey: string | null;
}

const GENERAL = "general";

/**
 * The candidate's notes, newest first, with a composer for writers.
 *
 * A note can be about the person or about the stage an application is at.
 * One thread rather than a thread per stage: a recruiter reads a person's
 * history top to bottom, and the label on each note says where it belongs.
 */
export function NotesThread({
  candidateId,
  notes,
  contexts,
  writable,
}: {
  candidateId: string;
  notes: Note[];
  contexts: NoteContext[];
  writable: boolean;
}) {
  const router = useRouter();
  const [body, setBody] = useState("");
  const [about, setAbout] = useState(GENERAL);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (busy || !body.trim()) return;
    setBusy(true);
    setError(null);
    const context = contexts.find((c) => c.value === about);
    try {
      const response = await fetch(`/api/candidates/${encodeURIComponent(candidateId)}/notes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          body: body.trim(),
          application_id: context?.applicationId ?? null,
          stage_key: context?.stageKey ?? null,
        }),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: unknown } | null;
        throw new Error(describeError(payload?.detail, response.status));
      }
      setBody("");
      setAbout(GENERAL);
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Notes</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {writable ? (
          <form onSubmit={submit} className="space-y-2">
            <Textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={3}
              maxLength={5000}
              placeholder="Add a note for the hiring team"
              aria-label="New note"
            />
            <div className="flex flex-wrap items-center gap-2">
              {contexts.length ? (
                <label className="flex items-center gap-2 text-xs text-slate-500">
                  About
                  <select
                    value={about}
                    onChange={(e) => setAbout(e.target.value)}
                    className="rounded-md border border-slate-200 bg-white px-2 py-1.5 text-sm text-slate-700"
                  >
                    <option value={GENERAL}>This candidate in general</option>
                    {contexts.map((c) => (
                      <option key={c.value} value={c.value}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}
              <Button type="submit" size="sm" disabled={busy || !body.trim()} className="ml-auto">
                {busy ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
                ) : (
                  <MessageSquarePlus className="mr-2 h-4 w-4" aria-hidden />
                )}
                Add note
              </Button>
            </div>
            {error ? <p className="text-sm font-medium text-rose-700">{error}</p> : null}
          </form>
        ) : null}

        {notes.length === 0 ? (
          <p className="text-sm text-slate-500">No notes yet.</p>
        ) : (
          <ul className="space-y-3">
            {notes.map((note) => (
              <li key={note.id} className="rounded-lg border border-slate-200 p-3 text-sm">
                <p className="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-xs text-slate-500">
                  <span className="font-medium text-slate-700">
                    {note.author_name ?? "Earlier note"}
                  </span>
                  <span>{formatDate(note.created_at)}</span>
                  {note.job_title ? (
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-slate-600">
                      {[note.job_title, note.stage_name].filter(Boolean).join(", ")}
                    </span>
                  ) : null}
                </p>
                <p className="mt-1 whitespace-pre-line text-slate-700">{note.body}</p>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
