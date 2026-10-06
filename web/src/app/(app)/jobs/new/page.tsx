import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { CopyFromJob } from "@/components/copy-from-job";
import { JobForm } from "@/components/job-form";
import { PageHeader } from "@/components/page-header";
import { MAX_PAGE_SIZE, getJob, listDepartments, listJobs } from "@/lib/data";
import { copyJobValues } from "@/lib/job-form";
import { JOBS_WRITE } from "@/lib/permissions";
import { hasPermission } from "@/lib/session";

export const dynamic = "force-dynamic";

/**
 * Create a job, blank or copied from an existing one (`?from=<id>`, ATS
 * Phase E).
 *
 * The redirect is a courtesy for anyone who reaches the URL directly; the
 * backend's read-only gate is what actually refuses the write. Sending a demo
 * visitor to the list is friendlier than rendering a form whose submit button
 * is guaranteed to 403.
 */
export default async function NewJobPage({ searchParams }: PageProps<"/jobs/new">) {
  if (!(await hasPermission(JOBS_WRITE))) redirect("/jobs");

  const { from } = await searchParams;
  const fromId = typeof from === "string" && /^\d+$/.test(from) ? from : null;
  const [source, jobs, departments] = await Promise.all([
    fromId ? getJob(fromId) : Promise.resolve(null),
    // Optional context: a failed list only hides the picker.
    listJobs(1, MAX_PAGE_SIZE).catch(() => null),
    listDepartments(),
  ]);

  return (
    <>
      <Link
        href="/jobs"
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        All jobs
      </Link>

      <PageHeader
        title="New job"
        description="Open roles are matched against every candidate in the database."
      />

      <div className="max-w-3xl">
        {jobs && jobs.results.length > 0 ? (
          <CopyFromJob
            jobs={jobs.results.map((job) => ({
              id: job.id,
              title: job.title,
              department: job.department ?? "",
            }))}
            selected={source ? String(source.id) : ""}
          />
        ) : null}
        <JobForm
          key={source ? `from-${source.id}` : "blank"}
          initial={source ? copyJobValues(source) : undefined}
          canDraft
          departments={departments.map((d) => d.name)}
        />
      </div>
    </>
  );
}
