import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { JobForm } from "@/components/job-form";
import { PageHeader } from "@/components/page-header";
import { canWrite } from "@/lib/session";

export const dynamic = "force-dynamic";

/**
 * Create a job.
 *
 * The redirect is a courtesy for anyone who reaches the URL directly; the
 * backend's read-only gate is what actually refuses the write. Sending a demo
 * visitor to the list is friendlier than rendering a form whose submit button
 * is guaranteed to 403.
 */
export default async function NewJobPage() {
  if (!(await canWrite())) redirect("/jobs");

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
        <JobForm />
      </div>
    </>
  );
}
