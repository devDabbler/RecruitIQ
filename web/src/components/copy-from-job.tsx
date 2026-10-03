"use client";

import { useRouter } from "next/navigation";

/**
 * "Start from an existing job" (ATS Phase E). A native select on purpose: it
 * is a one-shot choice that navigates, and the URL (`/jobs/new?from=7`)
 * carries it.
 */
export function CopyFromJob({
  jobs,
  selected,
}: {
  jobs: { id: number; title: string; department: string }[];
  selected: string;
}) {
  const router = useRouter();
  return (
    <div className="mb-6 flex flex-wrap items-center gap-3 text-sm">
      <label htmlFor="copy-from-job" className="font-medium text-slate-700">
        Start from an existing job
      </label>
      <select
        id="copy-from-job"
        value={selected}
        onChange={(e) =>
          router.push(e.target.value ? `/jobs/new?from=${e.target.value}` : "/jobs/new")
        }
        className="h-9 max-w-md min-w-0 flex-1 rounded-md border border-slate-200 bg-white px-2"
      >
        <option value="">Blank job</option>
        {jobs.map((job) => (
          <option key={job.id} value={String(job.id)}>
            {job.title}
            {job.department ? ` (${job.department})` : ""}
          </option>
        ))}
      </select>
    </div>
  );
}
