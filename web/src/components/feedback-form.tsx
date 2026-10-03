"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { RECOMMENDATIONS, RECOMMENDATION_LABELS } from "@/lib/interviews";
import { cn } from "@/lib/utils";

const CHOICE = "cursor-pointer rounded-md border px-2.5 py-1 text-sm";
const ON = "border-indigo-600 bg-indigo-600 text-white";
const OFF = "border-slate-200 bg-white text-slate-700 hover:border-indigo-300";

/** One interviewer's feedback on one stage. Final once submitted. */
export function FeedbackForm({ interviewId, stageName }: { interviewId: number; stageName: string }) {
  const router = useRouter();
  const [rating, setRating] = useState<number | null>(null);
  const [recommendation, setRecommendation] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    if (rating === null || recommendation === null) {
      setError("Choose a rating and a recommendation.");
      return;
    }
    setBusy(true);
    setError(null);
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
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="mt-3 space-y-3 rounded-md bg-slate-50 p-3">
      <p className="text-xs text-slate-600">
        Your feedback for {stageName}. It is final once submitted, and other interviewers see it
        only after giving their own.
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
                onChange={() => setRating(n)}
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
                onChange={() => setRecommendation(key)}
                className="sr-only"
              />
              {RECOMMENDATION_LABELS[key]}
            </label>
          ))}
        </div>
      </fieldset>
      <label className="block">
        <span className="text-xs font-medium text-slate-700">Notes (optional)</span>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={3}
          maxLength={5000}
          className="mt-1 w-full rounded-md border border-slate-200 bg-white p-2 text-sm text-slate-800"
        />
      </label>
      {error ? <p className="text-sm font-medium text-rose-700">{error}</p> : null}
      <Button type="submit" size="sm" disabled={busy}>
        {busy ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden /> : null}
        Submit feedback
      </Button>
    </form>
  );
}
