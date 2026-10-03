import Link from "next/link";

import { EmptyState, ErrorState, PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { listInterviews } from "@/lib/data";
import type { InterviewScope } from "@/lib/domain";
import { INTERVIEW_STATE_LABELS } from "@/lib/interviews";
import { getUser } from "@/lib/session";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

export const metadata = { title: "Interviews · RecruitIQ" };

const SCOPES: { key: InterviewScope; label: string }[] = [
  { key: "mine", label: "My interviews" },
  { key: "pending", label: "Waiting for feedback" },
  { key: "all", label: "All" },
];

const EMPTY: Record<InterviewScope, string> = {
  mine: "Nobody has assigned you an interview yet.",
  pending: "No feedback is outstanding.",
  all: "No interviews have been assigned yet.",
};

const STATE_CLASSES: Record<string, string> = {
  waiting: "border-amber-200 bg-amber-50 text-amber-700",
  upcoming: "border-slate-200 bg-slate-50 text-slate-600",
  submitted: "border-emerald-200 bg-emerald-50 text-emerald-700",
  skipped: "border-neutral-200 bg-neutral-100 text-neutral-500",
};

export default async function InterviewsPage({ searchParams }: PageProps<"/interviews">) {
  const params = await searchParams;
  const user = await getUser();
  const interviewer = user?.role === "interviewer";
  const requested = Array.isArray(params.scope) ? params.scope[0] : params.scope;
  // Signed-in staff start on their own list; the demo starts on everything.
  const fallback: InterviewScope = user && user.role !== "demo" ? "mine" : "all";
  const scope: InterviewScope = interviewer
    ? "mine"
    : SCOPES.some((s) => s.key === requested)
      ? (requested as InterviewScope)
      : fallback;

  let items;
  try {
    items = await listInterviews(scope);
  } catch (error) {
    return (
      <>
        <PageHeader title="Interviews" />
        <ErrorState
          title="Could not load interviews"
          detail={error instanceof ApiError ? error.detail : String(error)}
        />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Interviews"
        description={
          interviewer
            ? "The candidates you are interviewing. Their match scores appear once you submit your feedback."
            : "Who is interviewing whom, and whose feedback is still outstanding."
        }
      />
      {!interviewer ? (
        <nav aria-label="Interview views" className="mb-4 flex flex-wrap gap-2">
          {SCOPES.map((s) => (
            <Link
              key={s.key}
              href={`/interviews?scope=${s.key}`}
              aria-current={s.key === scope ? "page" : undefined}
              className={cn(
                "rounded-full border px-3 py-1 text-sm",
                s.key === scope
                  ? "border-indigo-600 bg-indigo-600 text-white"
                  : "border-slate-200 bg-white text-slate-600 hover:border-indigo-300",
              )}
            >
              {s.label}
            </Link>
          ))}
        </nav>
      ) : null}

      {items.length === 0 ? (
        <EmptyState title={EMPTY[scope]} />
      ) : (
        <Card>
          <CardContent className="p-0">
            <ul className="divide-y divide-slate-100">
              {items.map((item) => {
                const href = `/candidates/${item.candidate_id}#interviews-${item.application_id}`;
                const yours = item.interviewer_id === user?.id;
                return (
                  <li
                    key={item.id}
                    className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm sm:px-6"
                  >
                    <span className="min-w-0">
                      <Link href={href} className="block truncate font-medium text-slate-900 hover:underline">
                        {item.candidate_name}
                      </Link>
                      <span className="block truncate text-xs text-slate-500">
                        {item.job_title} · {item.stage_name}
                        {scope !== "mine" ? ` · ${item.interviewer_name}` : ""}
                      </span>
                    </span>
                    <span className="flex items-center gap-3">
                      <span className={cn("rounded-full border px-2.5 py-0.5 text-xs", STATE_CLASSES[item.state])}>
                        {INTERVIEW_STATE_LABELS[item.state]}
                      </span>
                      {yours && item.state === "waiting" ? (
                        <Link href={href} className="text-xs font-medium text-indigo-700 hover:underline">
                          Give feedback
                        </Link>
                      ) : null}
                    </span>
                  </li>
                );
              })}
            </ul>
          </CardContent>
        </Card>
      )}
    </>
  );
}
