"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Loader2, SkipForward, UserX, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ACTION_LABELS, type StageAction } from "@/lib/pipeline";

/**
 * Advance, Skip, Reject, Decline for one application.
 *
 * Reject and Decline ask for confirmation and an optional note because they
 * are terminal. The timeline is a Server Component, so a refresh is what
 * re-renders it after the API answers.
 */
export function StageActions({
  applicationId,
  actions,
  stageName,
}: {
  applicationId: number;
  actions: StageAction[];
  stageName: string;
}) {
  const router = useRouter();
  const [confirming, setConfirming] = useState<StageAction | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<StageAction | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(action: StageAction) {
    if (busy) return;
    setBusy(action);
    setError(null);
    try {
      const response = await fetch(`/api/applications/${applicationId}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note: note.trim() || null }),
      });
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
      if (!response.ok) {
        throw new Error(payload?.detail || `Could not ${action} (${response.status})`);
      }
      setConfirming(null);
      setNote("");
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  if (actions.length === 0) return null;

  if (confirming) {
    const terminal = confirming === "reject" ? "rejected" : "marked as declined";
    return (
      <div
        role="alertdialog"
        aria-label={`${ACTION_LABELS[confirming]}?`}
        className="space-y-3 rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm"
      >
        <p className="font-medium text-rose-900">
          {ACTION_LABELS[confirming]} at {stageName}?
        </p>
        <p className="text-rose-800">
          The application will be {terminal} and every later stage skipped. This cannot be undone
          from here.
        </p>
        <label className="block">
          <span className="text-xs font-medium text-rose-900">Reason (optional)</span>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={2}
            maxLength={2000}
            className="mt-1 w-full rounded-md border border-rose-200 bg-white p-2 text-sm text-slate-800"
          />
        </label>
        {error ? <p className="font-medium text-rose-900">{error}</p> : null}
        <div className="flex gap-2">
          <Button
            type="button"
            onClick={() => run(confirming)}
            disabled={busy !== null}
            className="bg-rose-600 text-white hover:bg-rose-700"
          >
            {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden /> : null}
            {ACTION_LABELS[confirming]}
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={busy !== null}
            onClick={() => {
              setConfirming(null);
              setError(null);
            }}
          >
            Keep them here
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        {actions.includes("advance") ? (
          <Button type="button" onClick={() => run("advance")} disabled={busy !== null}>
            {busy === "advance" ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <ArrowRight className="mr-2 h-4 w-4" aria-hidden />
            )}
            Advance
          </Button>
        ) : null}
        {actions.includes("skip") ? (
          <Button type="button" variant="outline" onClick={() => run("skip")} disabled={busy !== null}>
            {busy === "skip" ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <SkipForward className="mr-2 h-4 w-4" aria-hidden />
            )}
            Skip stage
          </Button>
        ) : null}
        {actions.includes("decline") ? (
          <Button
            type="button"
            variant="outline"
            onClick={() => setConfirming("decline")}
            disabled={busy !== null}
          >
            <UserX className="mr-2 h-4 w-4" aria-hidden />
            Candidate declined
          </Button>
        ) : null}
        {actions.includes("reject") ? (
          <Button
            type="button"
            variant="outline"
            onClick={() => setConfirming("reject")}
            disabled={busy !== null}
            className="border-slate-200 text-slate-600 hover:border-rose-300 hover:bg-rose-50 hover:text-rose-700"
          >
            <X className="mr-2 h-4 w-4" aria-hidden />
            Reject
          </Button>
        ) : null}
      </div>
      {error ? <p className="text-sm font-medium text-rose-700">{error}</p> : null}
    </div>
  );
}
