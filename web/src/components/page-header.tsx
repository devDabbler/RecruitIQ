import type { ReactNode } from "react";

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">{title}</h1>
        {description ? <p className="mt-1 text-sm text-slate-600">{description}</p> : null}
      </div>
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </div>
  );
}

/**
 * Shown when the API is unreachable or errors.
 *
 * Deliberately concrete: "is uvicorn running" is the actual cause nine times
 * out of ten in development, and a generic "something went wrong" would send
 * someone reading frontend code for a backend problem.
 */
export function ErrorState({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="rounded-lg border border-rose-200 bg-rose-50 p-6">
      <h2 className="font-medium text-rose-900">{title}</h2>
      <p className="mt-1 text-sm text-rose-700">{detail}</p>
    </div>
  );
}

export function EmptyState({ title, detail }: { title: string; detail?: string }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center">
      <p className="font-medium text-slate-700">{title}</p>
      {detail ? <p className="mt-1 text-sm text-slate-500">{detail}</p> : null}
    </div>
  );
}
