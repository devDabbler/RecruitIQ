import { type ApplicantFit, type FitTone, fitDisplay } from "@/lib/fit";

const TONES: Record<FitTone, string> = {
  strong: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  moderate: "bg-amber-50 text-amber-700 ring-amber-200",
  weak: "bg-slate-100 text-slate-600 ring-slate-200",
  none: "bg-white text-slate-400 ring-slate-200",
};

/**
 * An applicant's fit score as a small chip, with a "capped" hint when a
 * requirement held it down. `compact` leaves the hint to the caller (the
 * board card says what was missing on a line of its own).
 */
export function FitChip({
  fit,
  compact = false,
}: {
  fit: ApplicantFit | null | undefined;
  compact?: boolean;
}) {
  const shown = fitDisplay(fit);
  return (
    <span className="inline-flex shrink-0 items-center gap-1" title={shown.title}>
      <span
        aria-hidden
        className={`inline-flex min-w-8 justify-center rounded px-1.5 py-0.5 text-xs font-semibold tabular-nums ring-1 ring-inset ${TONES[shown.tone]}`}
      >
        {shown.text}
      </span>
      {shown.capped && !compact ? (
        <span aria-hidden className="text-[11px] font-medium text-rose-600">
          capped
        </span>
      ) : null}
      <span className="sr-only">{shown.title}</span>
    </span>
  );
}
