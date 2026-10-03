import Link from "next/link";

import type { JobPipeline } from "@/lib/domain";

/**
 * One column per enabled round, candidates as chips, outcomes as a footer.
 *
 * Horizontal scroll rather than wrapping: nine columns never fit, and a
 * board that wraps stops reading left to right as a funnel.
 */
export function PipelineBoard({ pipeline }: { pipeline: JobPipeline }) {
  const active = pipeline.columns.reduce((n, c) => n + c.applications.length, 0);
  const outcomes = pipeline.outcomes;

  return (
    <div className="space-y-3">
      <p className="text-xs text-slate-500">
        {active} in progress · {outcomes.hired ?? 0} hired · {outcomes.rejected ?? 0} rejected ·{" "}
        {outcomes.declined ?? 0} declined
      </p>
      <div className="flex gap-3 overflow-x-auto pb-2">
        {pipeline.columns.map((column) => (
          <section
            key={column.stage_key}
            aria-label={column.stage_name}
            className="w-44 shrink-0 rounded-lg border border-slate-200 bg-slate-50"
          >
            <header className="flex items-baseline justify-between gap-2 border-b border-slate-200 px-3 py-2">
              <h3 className="truncate text-xs font-medium text-slate-700">{column.stage_name}</h3>
              <span className="text-xs text-slate-400">{column.applications.length}</span>
            </header>
            <ul className="space-y-1.5 p-2">
              {column.applications.length === 0 ? (
                <li className="px-1 py-2 text-center text-xs text-slate-300">Empty</li>
              ) : (
                column.applications.map((card) => (
                  <li key={card.application_id}>
                    <Link
                      href={`/candidates/${card.candidate_id}`}
                      className="block rounded-md border border-slate-200 bg-white px-2.5 py-2 text-sm hover:border-indigo-300 hover:bg-indigo-50"
                    >
                      <span className="block truncate font-medium text-slate-800">
                        {card.candidate_name}
                      </span>
                      {card.current_position ? (
                        <span className="block truncate text-xs text-slate-500">
                          {card.current_position}
                        </span>
                      ) : null}
                    </Link>
                  </li>
                ))
              )}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}
