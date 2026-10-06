"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { FeedbackDraft, FeedbackTemplate } from "@/lib/domain";
import { AUTOSAVE_MS, applyTemplate, draftSavedLabel, feedbackShortcut } from "@/lib/feedback";
import { RECOMMENDATIONS, RECOMMENDATION_LABELS } from "@/lib/interviews";
import { cn } from "@/lib/utils";

const CHOICE = "cursor-pointer rounded-md border px-2.5 py-1 text-sm";
const ON = "border-indigo-600 bg-indigo-600 text-white";
const OFF = "border-slate-200 bg-white text-slate-700 hover:border-indigo-300";

/**
 * One interviewer's feedback on one stage. Final once submitted.
 *
 * Track 2 Phase 4: starts from the interviewer's saved draft, autosaves a
 * draft (seen by nobody else) shortly after each change, offers the job's
 * templates then the global ones, and takes 1-5 for the rating (outside the
 * notes box) and Ctrl/Cmd+Enter to submit.
 */
export function FeedbackForm({
  interviewId,
  stageName,
  draft = null,
  templates = [],
}: {
  interviewId: number;
  stageName: string;
  draft?: FeedbackDraft | null;
  templates?: FeedbackTemplate[];
}) {
  const router = useRouter();
  const formRef = useRef<HTMLFormElement>(null);
  const [rating, setRating] = useState<number | null>(draft?.rating ?? null);
  const [recommendation, setRecommendation] = useState<string | null>(draft?.recommendation ?? null);
  const [notes, setNotes] = useState(draft?.notes ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(draft?.updated_at ?? null);
  const [saving, setSaving] = useState(false);
  // Autosave runs only after the interviewer changes something, and never
  // once submit has started (a late draft save would 409 anyway).
  const dirty = useRef(false);
  const submitted = useRef(false);
  // The body of a change not yet sent. Flushed on page hide so leaving
  // inside the debounce window does not lose the last edit.
  const unsaved = useRef<string | null>(null);

  useEffect(() => {
    function flush() {
      if (unsaved.current === null || submitted.current) return;
      void fetch(`/api/interviews/${interviewId}/feedback`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: unsaved.current,
        keepalive: true,
      }).catch(() => undefined);
      unsaved.current = null;
    }
    window.addEventListener("pagehide", flush);
    return () => {
      window.removeEventListener("pagehide", flush);
      flush(); // client-side navigation away unmounts the form
    };
  }, [interviewId]);

  useEffect(() => {
    if (!dirty.current || submitted.current) return;
    const body = JSON.stringify({ rating, recommendation, notes });
    unsaved.current = body;
    const timer = window.setTimeout(async () => {
      if (submitted.current) return;
      unsaved.current = null;
      setSaving(true);
      try {
        const response = await fetch(`/api/interviews/${interviewId}/feedback`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body,
        });
        const payload = (await response.json().catch(() => null)) as {
          detail?: unknown;
          draft?: FeedbackDraft | null;
        } | null;
        if (submitted.current) return;
        if (!response.ok) {
          setError(
            typeof payload?.detail === "string" ? payload.detail : `Could not save the draft (${response.status})`,
          );
          return;
        }
        setError(null);
        setSavedAt(payload?.draft?.updated_at ?? new Date().toISOString());
      } catch {
        if (!submitted.current) setError("Could not save the draft. Check your connection.");
      } finally {
        setSaving(false);
      }
    }, AUTOSAVE_MS);
    return () => window.clearTimeout(timer);
  }, [interviewId, rating, recommendation, notes]);

  function change<T>(setter: (value: T) => void) {
    return (value: T) => {
      dirty.current = true;
      setter(value);
    };
  }
  const chooseRating = change(setRating);
  const chooseRecommendation = change(setRecommendation);
  const editNotes = change(setNotes);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    if (rating === null || recommendation === null) {
      setError("Choose a rating and a recommendation.");
      return;
    }
    setBusy(true);
    setError(null);
    submitted.current = true;
    try {
      const response = await fetch(`/api/interviews/${interviewId}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating, recommendation, notes }),
      });
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
      if (!response.ok) throw new Error(payload?.detail || `Could not submit (${response.status})`);
      router.refresh();
    } catch (err) {
      submitted.current = false;
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLFormElement>) {
    const target = e.target as HTMLElement;
    const shortcut = feedbackShortcut({
      key: e.key,
      ctrlKey: e.ctrlKey,
      metaKey: e.metaKey,
      altKey: e.altKey,
      inTextField: target.tagName === "TEXTAREA" || target.tagName === "SELECT",
    });
    if (shortcut === null) return;
    e.preventDefault();
    if (shortcut.kind === "submit") formRef.current?.requestSubmit();
    else chooseRating(shortcut.value);
  }

  return (
    <form
      ref={formRef}
      onSubmit={submit}
      onKeyDown={onKeyDown}
      className="mt-3 space-y-3 rounded-md bg-slate-50 p-3"
    >
      <p className="text-xs text-slate-600">
        Your feedback for {stageName}. Drafts save as you go and only you can see them. It is final
        once submitted, and other interviewers see it only after giving their own.
      </p>
      <fieldset>
        <legend className="mb-1 text-xs font-medium text-slate-700">Rating</legend>
        <div className="flex gap-1">
          {[1, 2, 3, 4, 5].map((n) => (
            <label key={n} className={cn(CHOICE, "grid w-9 place-items-center", rating === n ? ON : OFF)}>
              <input
                type="radio"
                name={`rating-${interviewId}`}
                value={n}
                checked={rating === n}
                onChange={() => chooseRating(n)}
                className="sr-only"
              />
              {n}
            </label>
          ))}
        </div>
      </fieldset>
      <fieldset>
        <legend className="mb-1 text-xs font-medium text-slate-700">Recommendation</legend>
        <div className="flex flex-wrap gap-1">
          {RECOMMENDATIONS.map((key) => (
            <label key={key} className={cn(CHOICE, recommendation === key ? ON : OFF)}>
              <input
                type="radio"
                name={`recommendation-${interviewId}`}
                value={key}
                checked={recommendation === key}
                onChange={() => chooseRecommendation(key)}
                className="sr-only"
              />
              {RECOMMENDATION_LABELS[key]}
            </label>
          ))}
        </div>
      </fieldset>
      <div>
        <div className="flex flex-wrap items-end justify-between gap-2">
          <label htmlFor={`notes-${interviewId}`} className="text-xs font-medium text-slate-700">
            Notes (optional)
          </label>
          {templates.length > 0 ? (
            <select
              aria-label="Start from a template"
              value=""
              onChange={(e) => {
                const chosen = templates.find((t) => String(t.id) === e.target.value);
                if (chosen) editNotes(applyTemplate(notes, chosen.body));
              }}
              className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700"
            >
              <option value="">Start from a template</option>
              {templates.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                  {t.job_id ? " (this job)" : ""}
                </option>
              ))}
            </select>
          ) : null}
        </div>
        <textarea
          id={`notes-${interviewId}`}
          value={notes}
          onChange={(e) => editNotes(e.target.value)}
          rows={notes.split("\n").length > 4 ? 8 : 3}
          maxLength={5000}
          className="mt-1 w-full rounded-md border border-slate-200 bg-white p-2 text-sm text-slate-800"
        />
      </div>
      {error ? <p className="text-sm font-medium text-rose-700">{error}</p> : null}
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" size="sm" disabled={busy}>
          {busy ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden /> : null}
          Submit feedback
        </Button>
        <span className="text-xs text-slate-500" aria-live="polite">
          {saving ? "Saving draft..." : savedAt ? draftSavedLabel(savedAt) : null}
        </span>
        <span className="ml-auto hidden text-xs text-slate-400 sm:inline">
          Keys: 1-5 to rate, Ctrl+Enter to submit
        </span>
      </div>
    </form>
  );
}
