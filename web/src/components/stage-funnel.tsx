import type { FunnelRow } from "@/lib/domain";
import { formatShare, funnelWidth } from "@/lib/reports";

/**
 * Each round twice: how many applications ever reached it (light bar) and
 * how many are there right now (dark bar), on one shared scale. A stage
 * people move through quickly reads as a wide light bar with a thin dark one.
 * The numbers are printed above the bars, so the bars can stay aria-hidden.
 * Name and counts share a line and the bar sits under them, so the bar keeps
 * its width on a phone.
 */
export function StageFunnel({ rows, showShare = false }: { rows: FunnelRow[]; showShare?: boolean }) {
  if (rows.length === 0) {
    return <p className="text-sm text-slate-500">No applications yet.</p>;
  }
  const largest = Math.max(1, ...rows.map((row) => row.ever_reached));

  return (
    <div className="space-y-3">
      <ul className="space-y-3">
        {rows.map((row) => (
          <li key={row.key}>
            <div className="flex items-baseline justify-between gap-3">
              <span className="min-w-0 truncate text-sm text-slate-600" title={row.name}>
                {row.name}
              </span>
              <span className="shrink-0 text-xs whitespace-nowrap text-slate-500 tabular-nums">
                <span className="font-medium text-slate-900">{row.currently_here}</span> here ·{" "}
                {row.ever_reached} reached
                {showShare ? <> · {formatShare(row.share_of_applicants)}</> : null}
              </span>
            </div>
            <span
              className="relative mt-1 block h-2.5 overflow-hidden rounded-full bg-slate-100"
              aria-hidden
            >
              <span
                className="absolute inset-y-0 left-0 rounded-full bg-indigo-200"
                style={{ width: funnelWidth(row.ever_reached, largest) }}
              />
              <span
                className="absolute inset-y-0 left-0 rounded-full bg-indigo-600"
                style={{ width: funnelWidth(row.currently_here, largest) }}
              />
            </span>
          </li>
        ))}
      </ul>
      <p className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-3 rounded-full bg-indigo-600" aria-hidden />
          Here now
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-3 rounded-full bg-indigo-200" aria-hidden />
          Ever reached
        </span>
        {showShare ? <span>Percent is the share of all applicants who reached the stage.</span> : null}
      </p>
    </div>
  );
}
