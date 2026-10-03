import { Check, Circle, CircleDot, X } from "lucide-react";

import type { PublicStatus } from "@/lib/domain";
import { PUBLIC_STATE_LABELS, greeting } from "@/lib/public-status";
import { cn } from "@/lib/utils";

const ICONS = { done: Check, current: CircleDot, upcoming: Circle, closed: X } as const;

const ICON_CLASSES: Record<string, string> = {
  done: "text-emerald-600",
  current: "text-indigo-600",
  upcoming: "text-slate-300",
  closed: "text-slate-400",
};

/**
 * What a candidate sees: greeting, job, status, and the stage list with the
 * candidate-facing descriptions. Rendered from the allowlisted API shape
 * only; there is nothing else to render.
 */
export function PublicStatusView({ status }: { status: PublicStatus }) {
  return (
    <article className="space-y-6">
      <header className="space-y-2">
        <p className="text-sm text-slate-500">{greeting(status.first_name)}</p>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          Your application for {status.job_title}
        </h1>
        <p className="text-sm text-slate-600">
          {status.department ? `${status.department} · ` : ""}
          <span className="font-medium text-slate-800">{status.status}</span>
        </p>
      </header>

      <ol className="space-y-1 rounded-lg border border-slate-200 bg-white p-4">
        {status.stages.map((stage, index) => {
          const Icon = ICONS[stage.state as keyof typeof ICONS] ?? Circle;
          const isCurrent = stage.state === "current";
          return (
            <li
              key={`${index}-${stage.name}`}
              className={cn(
                "flex items-start gap-3 rounded-md px-2 py-2 text-sm",
                isCurrent && "bg-indigo-50",
              )}
            >
              <Icon
                className={cn("mt-0.5 h-4 w-4 shrink-0", ICON_CLASSES[stage.state])}
                aria-hidden
              />
              <span className="min-w-0 flex-1">
                <span
                  className={cn("block", isCurrent ? "font-medium text-slate-900" : "text-slate-700")}
                >
                  {stage.name}
                </span>
                {stage.description && stage.state !== "closed" ? (
                  <span className="block text-xs text-slate-500">{stage.description}</span>
                ) : null}
              </span>
              <span className="shrink-0 text-xs text-slate-400">
                {PUBLIC_STATE_LABELS[stage.state] ?? ""}
              </span>
            </li>
          );
        })}
      </ol>

      <p className="text-xs text-slate-500">
        This page shows where your application stands. It never includes interview notes, feedback,
        or scores. If you have a question, reply to the email that brought you here.
      </p>
    </article>
  );
}
