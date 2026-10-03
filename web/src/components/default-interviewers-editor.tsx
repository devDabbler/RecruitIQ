"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, X } from "lucide-react";

import type { StageDefaults } from "@/lib/domain";

/**
 * Who is assigned automatically when a candidate reaches each round of this
 * job. Read-only unless `editable` (jobs.write); the API checks either way.
 */
export function DefaultInterviewersEditor({
  jobId,
  stages,
  team,
  editable,
}: {
  jobId: number;
  stages: StageDefaults[];
  team: { id: string; name: string }[];
  editable: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function save(stageKey: string, userIds: string[]) {
    setBusy(stageKey);
    setError(null);
    try {
      const response = await fetch(`/api/jobs/${jobId}/stages/${stageKey}/default-interviewers`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_ids: userIds }),
      });
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
      if (!response.ok) throw new Error(payload?.detail || `Could not save (${response.status})`);
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-2">
      <ul className="divide-y divide-slate-100 text-sm">
        {stages.map((stage) => {
          const ids = stage.users.map((u) => u.id);
          const available = team.filter((m) => !ids.includes(m.id));
          return (
            <li key={stage.stage_key} className="flex flex-wrap items-center gap-2 py-2 first:pt-0 last:pb-0">
              <span className="w-44 shrink-0 text-slate-700">{stage.stage_name}</span>
              {stage.users.length === 0 && !editable ? (
                <span className="text-xs text-slate-400">Nobody</span>
              ) : null}
              {stage.users.map((u) => (
                <span
                  key={u.id}
                  className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-700"
                >
                  {u.name}
                  {editable ? (
                    <button
                      type="button"
                      aria-label={`Remove ${u.name} from ${stage.stage_name}`}
                      disabled={busy !== null}
                      onClick={() => save(stage.stage_key, ids.filter((id) => id !== u.id))}
                      className="text-slate-400 hover:text-rose-600"
                    >
                      <X className="h-3 w-3" aria-hidden />
                    </button>
                  ) : null}
                </span>
              ))}
              {editable && available.length > 0 ? (
                <select
                  aria-label={`Add a default interviewer for ${stage.stage_name}`}
                  value=""
                  disabled={busy !== null}
                  onChange={(e) => {
                    if (e.target.value) void save(stage.stage_key, [...ids, e.target.value]);
                  }}
                  className="h-7 rounded-md border border-slate-200 bg-white px-2 text-xs text-slate-600"
                >
                  <option value="">Add someone</option>
                  {available.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))}
                </select>
              ) : null}
              {busy === stage.stage_key ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-400" aria-hidden />
              ) : null}
            </li>
          );
        })}
      </ul>
      {error ? <p className="text-sm font-medium text-rose-700">{error}</p> : null}
    </div>
  );
}
