import { cn } from "@/lib/utils";

/**
 * A 0–100 match score.
 *
 * The API returns skill/role/experience sub-scores alongside the headline
 * number, and showing them is the point: a recruiter needs to know *why* a
 * ranking happened before acting on it, and an unexplained score is one nobody
 * trusts twice.
 */
export function MatchScore({ score, className }: { score: number; className?: string }) {
  const pct = Math.round(clamp(score));
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <span className="h-2 w-16 overflow-hidden rounded-full bg-slate-100">
        <span className={cn("block h-full rounded-full", band(pct))} style={{ width: `${pct}%` }} />
      </span>
      <span className="w-9 text-right text-sm font-semibold tabular-nums">{pct}%</span>
    </span>
  );
}

export function SubScore({ label, score }: { label: string; score: number | null | undefined }) {
  if (score === null || score === undefined) return null;
  const pct = Math.round(clamp(score));
  return (
    <span className="flex items-center gap-2 text-xs text-slate-500">
      <span className="w-20 shrink-0">{label}</span>
      <span className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-100">
        <span className={cn("block h-full rounded-full", band(pct))} style={{ width: `${pct}%` }} />
      </span>
      <span className="tabular-nums">{pct}</span>
    </span>
  );
}

function clamp(score: number): number {
  return Math.min(100, Math.max(0, score));
}

// Explicit class strings — Tailwind scans source text, so a class assembled at
// runtime never makes it into the stylesheet.
function band(pct: number): string {
  if (pct >= 75) return "bg-emerald-500";
  if (pct >= 50) return "bg-blue-500";
  if (pct >= 25) return "bg-amber-500";
  return "bg-slate-400";
}
