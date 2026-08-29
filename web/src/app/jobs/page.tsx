import Link from "next/link";
import { MapPin, Pencil, Plus, Users } from "lucide-react";

import { DeleteJobButton } from "@/components/delete-job-button";
import { EmptyState, ErrorState, PageHeader } from "@/components/page-header";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { listJobs } from "@/lib/data";
import type { JobList } from "@/lib/domain";
import { formatSalary, humanize } from "@/lib/format";
import { canWrite } from "@/lib/session";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

const STATUS_CLASSES: Record<string, string> = {
  open: "bg-emerald-50 text-emerald-700 border-emerald-200",
  draft: "bg-slate-100 text-slate-600 border-slate-200",
  on_hold: "bg-amber-50 text-amber-700 border-amber-200",
  filled: "bg-blue-50 text-blue-700 border-blue-200",
  closed: "bg-neutral-100 text-neutral-600 border-neutral-200",
  cancelled: "bg-rose-50 text-rose-700 border-rose-200",
};

export default async function JobsPage() {
  // Resolved before the fetch so the "New job" button is still offered on the
  // error path, where creating a role is a plausible next move.
  const writable = await canWrite();

  let jobs: JobList;
  try {
    jobs = await listJobs();
  } catch (error) {
    return (
      <>
        <PageHeader title="Jobs" actions={writable ? <NewJobButton /> : null} />
        <ErrorState
          title="Could not load jobs"
          detail={error instanceof ApiError ? error.detail : String(error)}
        />
      </>
    );
  }

  // Open roles first, then everything else — a recruiter's attention belongs on
  // what they can actually fill.
  const sorted = [...jobs.results].sort((a, b) => {
    if (a.status === b.status) return a.title.localeCompare(b.title);
    return a.status === "open" ? -1 : b.status === "open" ? 1 : 0;
  });

  return (
    <>
      <PageHeader
        title="Jobs"
        description={`${jobs.results.filter((j) => j.status === "open").length} open of ${jobs.total} total`}
        actions={writable ? <NewJobButton /> : null}
      />

      {sorted.length === 0 ? (
        <EmptyState
          title="No jobs yet"
          detail={
            writable
              ? "Create one above, or run scripts/seed_demo.py to populate the demo."
              : "Run scripts/seed_demo.py to populate the demo."
          }
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {sorted.map((job) => (
            <Card key={job.id} className="transition-shadow hover:shadow-md">
              <CardContent className="flex h-full flex-col gap-3 p-5">
                <div className="flex items-start justify-between gap-3">
                  <Link href={`/jobs/${job.id}`} className="font-medium hover:underline">
                    {job.title}
                  </Link>
                  <span
                    className={cn(
                      "shrink-0 rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap",
                      STATUS_CLASSES[job.status] ?? "border-slate-200 bg-slate-50 text-slate-600",
                    )}
                  >
                    {humanize(job.status)}
                  </span>
                </div>

                <p className="text-sm text-slate-500">{job.department}</p>

                <p className="line-clamp-3 text-sm text-slate-600">{job.job_overview}</p>

                <div className="mt-auto space-y-1.5 pt-2 text-xs text-slate-500">
                  <span className="flex items-center gap-1.5">
                    <MapPin className="h-3.5 w-3.5" aria-hidden />
                    {[job.location, humanize(job.location_type)].filter(Boolean).join(" · ")}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Users className="h-3.5 w-3.5" aria-hidden />
                    {job.applications} {job.applications === 1 ? "applicant" : "applicants"}
                  </span>
                  <span className="block font-medium text-slate-600">
                    {formatSalary(job.min_salary, job.max_salary)}
                  </span>
                </div>

                {writable ? (
                  <div className="flex items-center gap-2 border-t border-slate-100 pt-3">
                    <Link
                      href={`/jobs/${job.id}/edit`}
                      className={buttonVariants({ variant: "outline", size: "sm" })}
                    >
                      <Pencil className="mr-1.5 h-3.5 w-3.5" aria-hidden />
                      Edit
                    </Link>
                    <DeleteJobButton jobId={job.id} title={job.title} />
                  </div>
                ) : null}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}

function NewJobButton() {
  return (
    <Link href="/jobs/new" className={buttonVariants()}>
      <Plus className="mr-1.5 h-4 w-4" aria-hidden />
      New job
    </Link>
  );
}
