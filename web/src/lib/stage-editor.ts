/**
 * The stage editor's rules (ATS Phase E), pure and tested.
 *
 * Which stages may move comes from the API (`movable`), never from keys
 * hard-coded here, so the server's pinning rule is the only one.
 */
import type { PipelineUpdate, StageOut } from "./domain";

export interface EditableStage {
  key: string;
  name: string;
  description: string;
  enabled: boolean;
  kind: string;
  custom: boolean;
  movable: boolean;
}

export interface PendingStage {
  name: string;
  description: string;
  afterKey: string | null;
}

const FIRST_STAGE = "resume_submitted";

export function toEditable(stages: StageOut[]): EditableStage[] {
  return [...stages]
    .sort((a, b) => a.position - b.position)
    .map((s) => ({
      key: s.key,
      name: s.name,
      description: s.description ?? "",
      enabled: s.enabled,
      kind: s.kind,
      custom: s.custom ?? false,
      movable: s.movable ?? false,
    }));
}

export function moveStage(stages: EditableStage[], key: string, direction: -1 | 1): EditableStage[] {
  const index = stages.findIndex((s) => s.key === key);
  const target = index + direction;
  if (index === -1 || target < 0 || target >= stages.length) return stages;
  if (!stages[index].movable || !stages[target].movable) return stages;
  const next = [...stages];
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}

export function placementOptions(stages: EditableStage[]): { key: string; name: string }[] {
  return stages
    .filter((s) => s.key === FIRST_STAGE || s.movable)
    .map((s) => ({ key: s.key, name: s.name }));
}

export function buildUpdate(
  original: EditableStage[],
  edited: EditableStage[],
  added: PendingStage[],
  removed: string[],
): PipelineUpdate {
  const before = new Map(original.map((s) => [s.key, s]));
  const stages = edited
    .filter((s) => {
      const o = before.get(s.key);
      return o && (o.enabled !== s.enabled || o.name !== s.name || o.description !== s.description);
    })
    .map((s) => ({
      key: s.key,
      enabled: s.enabled,
      name: s.name.trim(),
      description: s.description.trim(),
    }));

  const originalOrder = original.filter((s) => s.movable && !removed.includes(s.key)).map((s) => s.key);
  const editedOrder = edited.filter((s) => s.movable).map((s) => s.key);
  const order = editedOrder.join("|") === originalOrder.join("|") ? null : editedOrder;

  return {
    stages,
    order,
    add: added.map((a) => ({
      name: a.name.trim(),
      description: a.description.trim() || null,
      after_key: a.afterKey,
    })),
    remove: removed,
  };
}

export function validateEdits(edited: EditableStage[], added: PendingStage[]): string | null {
  for (const s of edited) {
    if (!s.name.trim()) return "Every stage needs a name.";
    if (s.name.trim().length > 100) return "Stage names must be 100 characters or fewer.";
  }
  if (edited.some((s) => s.key === FIRST_STAGE && !s.enabled)) {
    return "Resume submitted cannot be turned off.";
  }
  if (added.some((a) => !a.name.trim() || a.name.trim().length > 100)) {
    return "New stage names must be between 1 and 100 characters.";
  }
  return null;
}
