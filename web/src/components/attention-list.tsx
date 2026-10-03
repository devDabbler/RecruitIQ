import Link from "next/link";

import type { PendingFeedbackRow, WaitingApplication } from "@/lib/domain";
import { daysLabel } from "@/lib/reports";

/**
 * The two things that go quiet without anyone noticing: candidates who have
 * not moved in a week, and interviews nobody wrote feedback for.
 */
export function AttentionList({
  waiting,
  waitingTotal,
  pending,
  reportsHref,
}: {
  waiting: WaitingApplication[];
  waitingTotal: number;
  pending: PendingFeedbackRow[];
  reportsHref?: string;
}) {
  if (waiting.length === 0 && pending.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        Nothing needs attention. Every active candidate moved in the last 7 days and no feedback is
        outstanding.
      </p>
    );
  }

  return (
    <div className="space-y-5">
      {waiting.length > 0 ? (
        <section>
          <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">
            No movement in 7+ days ({waitingTotal})
          </h3>
          <ul className="divide-y divide-slate-100 text-sm">
            {waiting.map((row) => (
              <li
                key={row.application_id}
                className="flex items-baseline justify-between gap-3 py-2 first:pt-0"
              >
                <span className="min-w-0">
                  <Link href={`/candidates/${row.candidate_id}`} className="font-medium hover:underline">
                    {row.candidate_name}
                  </Link>
                  <span className="block truncate text-xs text-slate-500">
                    {row.stage_name} · {row.job_title}
                  </span>
                </span>
                <span className="shrink-0 text-xs text-amber-700 tabular-nums">
                  {daysLabel(row.days_waiting)}
                </span>
              </li>
            ))}
          </ul>
          {reportsHref && waitingTotal > waiting.length ? (
            <Link href={reportsHref} className="mt-2 inline-block text-xs text-indigo-600 hover:underline">
              See all {waitingTotal} on Reports
            </Link>
          ) : null}
        </section>
      ) : null}

      {pending.length > 0 ? (
        <section>
          <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">
            Feedback not yet submitted
          </h3>
          <ul className="divide-y divide-slate-100 text-sm">
            {pending.map((row) => (
              <li
                key={row.interview_id}
                className="flex items-baseline justify-between gap-3 py-2 first:pt-0"
              >
                <span className="min-w-0">
                  <Link href={`/candidates/${row.candidate_id}`} className="font-medium hover:underline">
                    {row.candidate_name}
                  </Link>
                  <span className="block truncate text-xs text-slate-500">
                    {row.stage_name} · {row.interviewer_name ?? "Unnamed interviewer"}
                  </span>
                </span>
                <span className="shrink-0 text-xs text-slate-500 tabular-nums">
                  {daysLabel(row.days_pending)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
