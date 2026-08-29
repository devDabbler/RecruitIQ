import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { ArrowLeft, Pencil } from "lucide-react";

import { DeleteJobButton } from "@/components/delete-job-button";
import { MatchScore, SubScore } from "@/components/match-score";
import { PageHeader } from "@/components/page-header";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { getJob, matchCandidatesForJob } from "@/lib/data";
import { formatDate, formatSalary, humanize } from "@/lib/format";
import { canWrite } from "@/lib/session";

export const dynamic = "force-dynamic";

export default async function JobDetailPage({ params }: PageProps<"/jobs/[id]">) {
  const { id } = await params;
  const [job, writable] = await Promise.all([getJob(id), canWrite()]);
  if (!job) notFound();

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
        title={job.title}
        description={[job.department, job.location, humanize(job.location_type)]
          .filter(Boolean)
          .join(" · ")}
        actions={
          writable ? (
            <Link
              href={`/jobs/${job.id}/edit`}
              className={buttonVariants({ variant: "outline" })}
            >
              <Pencil className="mr-1.5 h-4 w-4" aria-hidden />
              Edit
            </Link>
          ) : null
        }
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Overview</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm whitespace-pre-line text-slate-700">{job.job_overview}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Required qualifications</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm whitespace-pre-line text-slate-700">
                {job.required_qualifications}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Matching candidates</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Streamed separately: matching is model-backed and takes ~9s,
                  and awaiting it here held the whole navigation open for that
                  long — a click on a job card looked like a dead link. The
                  description now paints immediately and scores fill in. */}
              <Suspense fallback={<MatchesSkeleton />}>
                <Matches jobId={job.id} />
              </Suspense>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Details</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="space-y-3 text-sm">
                <Detail label="Status" value={humanize(job.status)} />
                <Detail label="Employment" value={humanize(job.job_type)} />
                <Detail label="Experience" value={humanize(job.experience_level)} />
                <Detail label="Salary" value={formatSalary(job.min_salary, job.max_salary)} />
                <Detail label="Hiring manager" value={job.hiring_manager} />
                <Detail label="Recruiter" value={job.recruiter} />
                <Detail label="Applicants" value={String(job.applications)} />
                <Detail label="Posted" value={formatDate(job.created_at)} />
                <Detail label="Deadline" value={formatDate(job.application_deadline)} />
              </dl>
            </CardContent>
          </Card>

          {job.skills?.length ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Required skills</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-1.5">
                {job.skills.map((skill) => (
                  <span
                    key={skill}
                    className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-700"
                  >
                    {skill}
                  </span>
                ))}
              </CardContent>
            </Card>
          ) : null}

          {writable ? <DeleteJobButton jobId={job.id} title={job.title} variant="full" /> : null}
        </div>
      </div>
    </>
  );
}

async function Matches({ jobId }: { jobId: number }) {
  // If matching fails, the job description still renders; an empty panel beats
  // a 500 on the whole route.
  const matches = await matchCandidatesForJob(jobId).catch(
    () => [] as Awaited<ReturnType<typeof matchCandidatesForJob>>,
  );

  if (matches.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        No candidate scored above the threshold for this role.
      </p>
    );
  }

  return (
    <>
      {matches.slice(0, 8).map((candidate) => (
        <div key={candidate.id} className="rounded-lg border border-slate-200 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Link href={`/candidates/${candidate.id}`} className="font-medium hover:underline">
              {candidate.name}
            </Link>
            <MatchScore score={candidate.match_score} />
          </div>
          <p className="mt-1 text-xs text-slate-500">
            {[
              candidate.position,
              candidate.years_experience
                ? `${candidate.years_experience} yrs`
                : candidate.experience_level,
            ]
              .filter(Boolean)
              .join(" · ") || "No details on file"}
          </p>
          <p className="mt-2 text-sm text-slate-600">{candidate.match_explanation}</p>
          <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1">
            <SubScore label="Skills" score={candidate.skill_match_score} />
            <SubScore label="Role" score={candidate.role_match_score} />
            <SubScore label="Experience" score={candidate.experience_match_score} />
          </div>
        </div>
      ))}
    </>
  );
}

function MatchesSkeleton() {
  return (
    <>
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} className="h-28 w-full rounded-lg" />
      ))}
    </>
  );
}

function Detail({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="shrink-0 text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-slate-800">{value || "Not specified"}</dd>
    </div>
  );
}
