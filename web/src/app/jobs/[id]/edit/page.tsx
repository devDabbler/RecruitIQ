import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { JobForm } from "@/components/job-form";
import { PageHeader } from "@/components/page-header";
import { getJob } from "@/lib/data";
import { jobToFormValues } from "@/lib/job-form";
import { canWrite } from "@/lib/session";

export const dynamic = "force-dynamic";

export default async function EditJobPage({ params }: PageProps<"/jobs/[id]/edit">) {
  const { id } = await params;
  if (!(await canWrite())) redirect(`/jobs/${id}`);

  const job = await getJob(id);
  if (!job) notFound();

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
        title="Edit job"
        description="Changes to the title and skills take effect on the next match run."
      />

      <div className="max-w-3xl">
        <JobForm initial={jobToFormValues(job)} jobId={job.id} />
      </div>
    </>
  );
}
