import Link from "next/link";
import { Check, Circle, CircleDot, Minus, X } from "lucide-react";

import { StageActions } from "@/components/stage-actions";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ApplicationDetail } from "@/lib/domain";
import { formatDate } from "@/lib/format";
import { APPLICATION_STATUS_LABELS, STAGE_STATUS_LABELS, availableActions } from "@/lib/pipeline";
import { cn } from "@/lib/utils";

const ICONS = {
  pending: Circle,
  in_progress: CircleDot,
  passed: Check,
  failed: X,
  skipped: Minus,
} as const;

const ICON_CLASSES: Record<string, string> = {
  pending: "text-slate-300",
  in_progress: "text-indigo-600",
  passed: "text-emerald-600",
  failed: "text-rose-600",
  skipped: "text-slate-400",
};

/**
 * One application's journey through its job's pipeline.
 *
 * Disabled stages are hidden unless something already happened at them, so
 * a job that turned off Case study does not show an empty row for it.
 */
export function ApplicationTimeline({
  application,
  writable,
}: {
  application: ApplicationDetail;
  writable: boolean;
}) {
  const actions = writable ? availableActions(application) : [];
  const current = application.stages.find((s) => s.status === "in_progress");
  const visible = application.stages.filter((s) => s.enabled || s.status !== "pending");

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-baseline justify-between gap-2">
        <CardTitle className="text-base">
          <Link href={`/jobs/${application.job_id}`} className="hover:underline">
            {application.job_title}
          </Link>
        </CardTitle>
        <span className="text-xs text-slate-500">
          {APPLICATION_STATUS_LABELS[application.status] ?? application.status}
          {application.applied_at ? ` · applied ${formatDate(application.applied_at)}` : ""}
        </span>
      </CardHeader>
      <CardContent className="space-y-4">
        <ol className="space-y-1">
          {visible.map((stage) => {
            const Icon = ICONS[stage.status as keyof typeof ICONS] ?? Circle;
            const isCurrent = stage.status === "in_progress";
            return (
              <li
                key={stage.key}
                className={cn(
                  "flex items-start gap-3 rounded-md px-2 py-1.5 text-sm",
                  isCurrent && "bg-indigo-50",
                )}
              >
                <Icon
                  className={cn("mt-0.5 h-4 w-4 shrink-0", ICON_CLASSES[stage.status])}
                  aria-hidden
                />
                <span className="min-w-0 flex-1">
                  <span
                    className={cn(
                      "block",
                      isCurrent ? "font-medium text-slate-900" : "text-slate-700",
                    )}
                  >
                    {stage.name}
                    {stage.kind === "outcome" ? (
                      <span className="ml-2 text-xs text-slate-400">outcome</span>
                    ) : null}
                  </span>
                  {isCurrent && stage.description ? (
                    <span className="block text-xs text-slate-500">{stage.description}</span>
                  ) : null}
                  {stage.note ? (
                    <span className="block text-xs text-slate-500">Note: {stage.note}</span>
                  ) : null}
                </span>
                <span className="shrink-0 text-xs text-slate-400">
                  <span className="sr-only">{STAGE_STATUS_LABELS[stage.status]}</span>
                  {stage.completed_at
                    ? formatDate(stage.completed_at)
                    : stage.started_at
                      ? `since ${formatDate(stage.started_at)}`
                      : ""}
                </span>
              </li>
            );
          })}
        </ol>
        {actions.length > 0 && current ? (
          <StageActions applicationId={application.id} actions={actions} stageName={current.name} />
        ) : null}
      </CardContent>
    </Card>
  );
}
