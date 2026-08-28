import { cn } from "@/lib/utils";
import { STAGE_CLASSES, STAGE_LABELS, isPipelineStage } from "@/lib/domain";

/**
 * A candidate's funnel position.
 *
 * Falls back to rendering the raw value for anything unrecognised rather than
 * hiding it: an unexpected status in the database is worth seeing, not
 * swallowing.
 */
export function StageBadge({
  status,
  className,
}: {
  status: string | null | undefined;
  className?: string;
}) {
  if (!status) {
    return <span className={cn("text-xs text-slate-400", className)}>—</span>;
  }

  const known = isPipelineStage(status);
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        known ? STAGE_CLASSES[status] : "border-slate-200 bg-slate-50 text-slate-600",
        className,
      )}
    >
      {known ? STAGE_LABELS[status] : status}
    </span>
  );
}
