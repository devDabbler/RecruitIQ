"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowDown, ArrowUp, Loader2, Plus, Save, Trash2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { StageOut } from "@/lib/domain";
import {
  buildUpdate,
  moveStage,
  placementOptions,
  toEditable,
  validateEdits,
  type EditableStage,
  type PendingStage,
} from "@/lib/stage-editor";

/**
 * Turn stages on and off, rename them, edit what candidates read, reorder
 * the interview stages, and add or remove stages this job added (ATS Phase
 * E). Saved in one request; the server refuses anything that would strand a
 * candidate.
 */
export function StageEditor({ jobId, stages }: { jobId: number; stages: StageOut[] }) {
  const router = useRouter();
  const original = useMemo(() => toEditable(stages), [stages]);
  const [edited, setEdited] = useState<EditableStage[]>(original);
  const [added, setAdded] = useState<PendingStage[]>([]);
  const [removed, setRemoved] = useState<string[]>([]);
  const [draft, setDraft] = useState<PendingStage>({ name: "", description: "", afterKey: null });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const rounds = edited.filter((s) => s.kind === "round");
  const outcomes = edited.filter((s) => s.kind === "outcome");

  function patch(key: string, change: Partial<EditableStage>) {
    setEdited((current) => current.map((s) => (s.key === key ? { ...s, ...change } : s)));
  }

  function remove(key: string) {
    setEdited((current) => current.filter((s) => s.key !== key));
    setRemoved((current) => [...current, key]);
  }

  function addPending() {
    if (!draft.name.trim()) {
      setError("Give the new stage a name.");
      return;
    }
    setAdded((current) => [...current, { ...draft, name: draft.name.trim() }]);
    setDraft({ name: "", description: "", afterKey: draft.afterKey });
    setError(null);
  }

  async function save() {
    const problem = validateEdits(edited, added);
    if (problem) {
      setError(problem);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`/api/jobs/${jobId}/pipeline`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildUpdate(original, edited, added, removed)),
      });
      const payload = (await response.json().catch(() => null)) as { detail?: unknown } | null;
      if (!response.ok) {
        throw new Error(
          typeof payload?.detail === "string"
            ? payload.detail
            : `Could not save the stages (${response.status})`,
        );
      }
      router.push(`/jobs/${jobId}`);
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <ol className="space-y-3">
        {rounds.map((stage, index) => (
          <li key={stage.key} className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="w-6 text-xs text-slate-400">{index + 1}</span>
              <Input
                value={stage.name}
                onChange={(e) => patch(stage.key, { name: e.target.value })}
                aria-label={`Name of stage ${index + 1}`}
                className="max-w-xs"
              />
              <label className="flex items-center gap-1.5 text-xs text-slate-600">
                <input
                  type="checkbox"
                  checked={stage.enabled}
                  disabled={stage.key === "resume_submitted"}
                  onChange={(e) => patch(stage.key, { enabled: e.target.checked })}
                />
                In use
              </label>
              <span className="ml-auto flex gap-1">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  aria-label={`Move ${stage.name} up`}
                  disabled={!stage.movable}
                  onClick={() => setEdited((current) => moveStage(current, stage.key, -1))}
                >
                  <ArrowUp className="h-3.5 w-3.5" aria-hidden />
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  aria-label={`Move ${stage.name} down`}
                  disabled={!stage.movable}
                  onClick={() => setEdited((current) => moveStage(current, stage.key, 1))}
                >
                  <ArrowDown className="h-3.5 w-3.5" aria-hidden />
                </Button>
                {stage.custom ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    aria-label={`Remove ${stage.name}`}
                    onClick={() => remove(stage.key)}
                  >
                    <Trash2 className="h-3.5 w-3.5" aria-hidden />
                  </Button>
                ) : null}
              </span>
            </div>
            <Textarea
              value={stage.description}
              onChange={(e) => patch(stage.key, { description: e.target.value })}
              rows={2}
              className="mt-2 text-sm"
              aria-label={`What candidates read about ${stage.name}`}
              placeholder="What candidates read about this stage on their status page."
            />
          </li>
        ))}
      </ol>

      <p className="text-xs text-slate-500">
        Resume submitted stays first and the offer stages stay last. Outcomes:{" "}
        {outcomes.map((s) => s.name).join(" and ")}.
      </p>

      <section className="space-y-2 rounded-lg border border-dashed border-slate-300 p-4">
        <h2 className="text-sm font-medium text-slate-800">Add a stage</h2>
        <div className="flex flex-wrap items-center gap-2">
          <Input
            value={draft.name}
            onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            placeholder="Portfolio review"
            aria-label="New stage name"
            className="max-w-xs"
          />
          <select
            value={draft.afterKey ?? ""}
            onChange={(e) => setDraft({ ...draft, afterKey: e.target.value || null })}
            className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm"
            aria-label="Place the new stage after"
          >
            <option value="">Just before the offer</option>
            {placementOptions(edited).map((option) => (
              <option key={option.key} value={option.key}>
                After {option.name}
              </option>
            ))}
          </select>
          <Button type="button" size="sm" variant="outline" onClick={addPending}>
            <Plus className="mr-1 h-3.5 w-3.5" aria-hidden />
            Add
          </Button>
        </div>
        {added.length > 0 ? (
          <ul className="space-y-1 text-xs text-slate-600">
            {added.map((a, i) => (
              <li key={`${a.name}-${i}`} className="flex items-center gap-2">
                Will add: {a.name}
                <button
                  type="button"
                  aria-label={`Do not add ${a.name}`}
                  className="text-slate-400 hover:text-slate-700"
                  onClick={() => setAdded((current) => current.filter((_, j) => j !== i))}
                >
                  <X className="h-3.5 w-3.5" aria-hidden />
                </button>
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      {error ? <p className="text-sm font-medium text-rose-700">{error}</p> : null}
      <Button type="button" onClick={save} disabled={busy}>
        {busy ? (
          <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
        ) : (
          <Save className="mr-2 h-4 w-4" aria-hidden />
        )}
        Save stages
      </Button>
    </div>
  );
}
