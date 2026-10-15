"use client";

import { useState } from "react";
import { Loader2, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { FeedbackSummary as Summary } from "@/lib/domain";
import { summaryStamp } from "@/lib/interviews";

const SECTIONS: { key: "themes" | "agreements" | "disagreements" | "open_questions"; title: string }[] = [
  { key: "themes", title: "Themes" },
  { key: "agreements", title: "Where they agree" },
  { key: "disagreements", title: "Where they differ" },
  { key: "open_questions", title: "Open questions" },
];

/**
 * A committee brief of the submitted feedback above it (Track 2 Phase 6).
 * Generated when asked and never saved, so it is labeled as AI output with
 * the time it was made. The panel only renders this when the viewer can read
 * every form; the API enforces the same rule.
 */
export function FeedbackSummary({ applicationId }: { applicationId: number }) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function generate() {
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`/api/applications/${applicationId}/feedback-summary`, {
        cache: "no-store",
      });
      const payload = (await response.json().catch(() => null)) as (Summary & { detail?: unknown }) | null;
      if (!response.ok || !payload) {
        const detail = typeof payload?.detail === "string" ? payload.detail : null;
        throw new Error(detail || `Could not summarize the feedback (${response.status}).`);
      }
      setSummary(payload);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-md border border-indigo-100 bg-indigo-50/40 p-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-medium text-slate-800">Feedback summary</span>
        <Button type="button" size="sm" variant="outline" onClick={generate} disabled={busy}>
          {busy ? <Loader2 className="animate-spin" /> : <Sparkles />}
          {summary ? "Summarize again" : "Summarize with AI"}
        </Button>
      </div>
      {!summary && !busy && !error ? (
        <p className="mt-1 text-xs text-slate-500">
          Themes, agreements, disagreements and open questions from the submitted forms. Names
          are removed before the model reads them.
        </p>
      ) : null}
      {busy && !summary ? <p className="mt-2 text-xs text-slate-500">Reading the feedback...</p> : null}
      {error ? (
        <p role="alert" className="mt-2 text-xs text-red-600">
          {error}
        </p>
      ) : null}
      {summary ? (
        <div className="mt-3 space-y-3">
          {summary.tally ? <p className="font-medium text-slate-700">{summary.tally}</p> : null}
          {SECTIONS.map(({ key, title }) => {
            const points = summary[key] ?? [];
            return points.length > 0 ? (
              <div key={key}>
                <h4 className="text-xs font-semibold tracking-wide text-slate-500 uppercase">{title}</h4>
                <ul className="mt-1 list-disc space-y-1 pl-5 text-slate-700">
                  {points.map((point, index) => (
                    <li key={index}>{point}</li>
                  ))}
                </ul>
              </div>
            ) : null;
          })}
          <p className="text-xs text-slate-400">
            {summaryStamp(summary.feedback_count, summary.generated_at)}
          </p>
        </div>
      ) : null}
    </div>
  );
}
