import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { StageEditor } from "@/components/stage-editor";
import { getJob, getJobPipeline } from "@/lib/data";
import { JOBS_WRITE } from "@/lib/permissions";
import { hasPermission } from "@/lib/session";

export const dynamic = "force-dynamic";

/** Edit one job's interview stages (ATS Phase E). Job writers only. */
export default async function EditStagesPage({ params }: PageProps<"/jobs/[id]/stages">) {
  const { id } = await params;
  if (!(await hasPermission(JOBS_WRITE))) redirect(`/jobs/${id}`);

  const [job, pipeline] = await Promise.all([getJob(id), getJobPipeline(id)]);
  if (!job || !pipeline) notFound();

  return (
    <>
      <Link
        href={`/jobs/${job.id}`}
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        Back to {job.title}
      </Link>
      <PageHeader
        title="Edit stages"
        description="Turn off rounds this job does not run, rename them, reorder interviews, or add your own."
      />
      <div className="max-w-3xl">
        <StageEditor jobId={job.id} stages={pipeline.stages} />
      </div>
    </>
  );
}
