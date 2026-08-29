"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";

/**
 * Delete a job, behind a confirmation that names it.
 *
 * The confirm step spells out what else goes: deleting a requisition also
 * removes its applications and saved-job records, which is not obvious from a
 * trash icon. Candidates sourced for the role are detached, not deleted, and
 * saying so is the difference between a recruiter clicking and not.
 */
export function DeleteJobButton({
  jobId,
  title,
  variant = "icon",
}: {
  jobId: number;
  title: string;
  variant?: "icon" | "full";
}) {
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function remove() {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`/api/jobs/${jobId}`, { method: "DELETE" });
      const payload = (await response.json().catch(() => null)) as {
        detail?: string;
        message?: string;
      } | null;
      if (!response.ok) {
        throw new Error(payload?.detail || `Could not delete the job (${response.status})`);
      }
      setConfirming(false);
      // The list is a Server Component, so a refresh is what re-renders it
      // without the deleted card.
      router.refresh();
      router.push("/jobs");
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  if (!confirming) {
    return (
      <Button
        type="button"
        variant="outline"
        size={variant === "icon" ? "icon" : "default"}
        onClick={() => setConfirming(true)}
        aria-label={`Delete ${title}`}
        className="border-slate-200 text-slate-500 hover:border-rose-300 hover:bg-rose-50 hover:text-rose-700"
      >
        <Trash2 className={variant === "icon" ? "h-4 w-4" : "mr-2 h-4 w-4"} aria-hidden />
        {variant === "full" ? "Delete job" : null}
      </Button>
    );
  }

  return (
    <div
      role="alertdialog"
      aria-label={`Delete ${title}?`}
      className="space-y-3 rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm"
    >
      <p className="font-medium text-rose-900">Delete &ldquo;{title}&rdquo;?</p>
      <p className="text-rose-800">
        This also removes its applications and saved-job records. Candidates sourced for the
        role are kept and simply detached from it. This cannot be undone.
      </p>
      {error ? <p className="font-medium text-rose-900">{error}</p> : null}
      <div className="flex gap-2">
        <Button
          type="button"
          onClick={remove}
          disabled={busy}
          className="bg-rose-600 text-white hover:bg-rose-700"
        >
          {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden /> : null}
          Delete
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={busy}
          onClick={() => {
            setConfirming(false);
            setError(null);
          }}
        >
          Keep it
        </Button>
      </div>
    </div>
  );
}
