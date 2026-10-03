"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, UserPlus } from "lucide-react";

import { Button } from "@/components/ui/button";

/** Put someone on a stage of this application. Writers only (the API checks). */
export function AssignInterviewer({
  applicationId,
  stages,
  team,
  defaultStage,
}: {
  applicationId: number;
  stages: { key: string; name: string }[];
  team: { id: string; name: string }[];
  defaultStage?: string;
}) {
  const router = useRouter();
  const initialStage =
    defaultStage && stages.some((s) => s.key === defaultStage) ? defaultStage : (stages[0]?.key ?? "");
  const [stageKey, setStageKey] = useState(initialStage);
  const [personId, setPersonId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function assign() {
    if (busy) return;
    if (!stageKey || !personId) {
      setError("Choose a stage and a person.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`/api/applications/${applicationId}/interviews`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stage_key: stageKey, interviewer_id: personId }),
      });
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
      if (!response.ok) throw new Error(payload?.detail || `Could not assign (${response.status})`);
      setPersonId("");
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (stages.length === 0 || team.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <select
        aria-label="Stage"
        value={stageKey}
        onChange={(e) => setStageKey(e.target.value)}
        className="h-8 rounded-md border border-slate-200 bg-white px-2 text-sm"
      >
        {stages.map((s) => (
          <option key={s.key} value={s.key}>
            {s.name}
          </option>
        ))}
      </select>
      <select
        aria-label="Interviewer"
        value={personId}
        onChange={(e) => setPersonId(e.target.value)}
        className="h-8 rounded-md border border-slate-200 bg-white px-2 text-sm"
      >
        <option value="">Choose someone</option>
        {team.map((m) => (
          <option key={m.id} value={m.id}>
            {m.name}
          </option>
        ))}
      </select>
      <Button type="button" size="sm" variant="outline" onClick={assign} disabled={busy}>
        {busy ? (
          <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden />
        ) : (
          <UserPlus className="mr-1.5 h-3.5 w-3.5" aria-hidden />
        )}
        Assign
      </Button>
      {error ? <p className="w-full text-xs font-medium text-rose-700">{error}</p> : null}
    </div>
  );
}
