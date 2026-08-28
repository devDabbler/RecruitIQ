import Link from "next/link";
import { Suspense } from "react";

import { JobPicker } from "@/components/job-picker";
import { MatchScore, SubScore } from "@/components/match-score";
import { EmptyState, ErrorState, PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { listJobs, matchCandidatesForJob } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function MatchingPage({ searchParams }: PageProps<"/matching">) {
  const params = await searchParams;
  const raw = Array.isArray(params.job) ? params.job[0] : params.job;

  let jobs;
  try {
    jobs = await listJobs();
  } catch (error) {
    return (
      <>
        <PageHeader title="Matching" />
        <ErrorState
          title="Could not load jobs"
          detail={error instanceof ApiError ? error.detail : String(error)}
        />
      </>
    );
  }

  const open = jobs.results.filter((job) => job.status === "open");
  const choices = (open.length ? open : jobs.results).map((job) => ({
    id: job.id,
    title: job.title,
    department: job.department,
  }));

  // Default to the first role so the screen is never a bare dropdown — a demo
  // that shows nothing until you click is a demo that looks broken.
  const selected = choices.find((job) => String(job.id) === raw) ?? choices[0];

  return (
    <>
      <PageHeader
        title="Matching"
        description="Semantic ranking over pgvector embeddings, with the sub-scores that produced each number."
      />

      {choices.length === 0 ? (
        <EmptyState title="No jobs to match against" />
      ) : (
        <>
          <JobPicker jobs={choices} selected={String(selected.id)} />

          <Suspense key={selected.id} fallback={<Loading />}>
            <Results jobId={selected.id} />
          </Suspense>
        </>
      )}
    </>
  );
}

async function Results({ jobId }: { jobId: number }) {
  let matches;
  try {
    matches = await matchCandidatesForJob(jobId);
  } catch (error) {
    return (
      <div className="mt-6">
        <ErrorState
          title="Matching failed"
          detail={error instanceof ApiError ? error.detail : String(error)}
        />
      </div>
    );
  }

  if (matches.length === 0) {
    return (
      <div className="mt-6">
        <EmptyState
          title="No candidates scored above the threshold"
          detail="Try a role with more overlap against the seeded skill set."
        />
      </div>
    );
  }

  return (
    <div className="mt-6 space-y-3">
      {matches.map((candidate, index) => (
        <Card key={candidate.id}>
          <CardContent className="flex flex-col gap-3 p-5 sm:flex-row sm:items-start">
            <span className="w-8 shrink-0 text-lg font-semibold text-slate-300 tabular-nums">
              {index + 1}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <Link
                  href={`/candidates/${candidate.id}`}
                  className="font-medium hover:underline"
                >
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
                  candidate.email,
                ]
                  .filter(Boolean)
                  .join(" · ") || "—"}
              </p>
              <p className="mt-2 text-sm text-slate-600">{candidate.match_explanation}</p>

              <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1">
                <SubScore label="Skills" score={candidate.skill_match_score} />
                <SubScore label="Role" score={candidate.role_match_score} />
                <SubScore label="Experience" score={candidate.experience_match_score} />
              </div>

              {candidate.skills.length ? (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {candidate.skills.slice(0, 8).map((skill) => (
                    <span
                      key={skill}
                      className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600"
                    >
                      {skill}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function Loading() {
  return (
    <div className="mt-6 space-y-3">
      {[0, 1, 2, 3].map((i) => (
        <Skeleton key={i} className="h-32 w-full rounded-xl" />
      ))}
    </div>
  );
}
