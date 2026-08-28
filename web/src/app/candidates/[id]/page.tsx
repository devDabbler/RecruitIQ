import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, FileText, Mail, MapPin, Phone } from "lucide-react";

import { MatchScore, SubScore } from "@/components/match-score";
import { PageHeader } from "@/components/page-header";
import { StageBadge } from "@/components/stage-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  getCandidate,
  getCandidateApplications,
  getCandidateResumes,
  getCandidateSavedJobs,
  matchJobsForCandidate,
} from "@/lib/data";
import { fullName, initials } from "@/lib/domain";
import { formatDate } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function CandidateDetailPage({ params }: PageProps<"/candidates/[id]">) {
  const { id } = await params;
  const candidate = await getCandidate(id);
  if (!candidate) notFound();

  // The related lists are all optional context. One of them failing — matching
  // is the slow, model-backed one — should dim a card, not blank the profile.
  const [applications, savedJobs, resumes, matches] = await Promise.all([
    getCandidateApplications(id),
    getCandidateSavedJobs(id),
    getCandidateResumes(id),
    matchJobsForCandidate(id).catch(() => [] as Awaited<ReturnType<typeof matchJobsForCandidate>>),
  ]);

  return (
    <>
      <Link
        href="/candidates"
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        All candidates
      </Link>

      <PageHeader
        title={fullName(candidate)}
        description={
          [candidate.current_position, candidate.current_company].filter(Boolean).join(" at ") ||
          candidate.position_applied ||
          undefined
        }
        actions={<StageBadge status={candidate.status} className="px-3 py-1 text-sm" />}
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-1">
          <Card>
            <CardContent className="space-y-4 p-6">
              <div className="flex items-center gap-3">
                <span className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-slate-900 text-sm font-semibold text-white">
                  {initials(candidate)}
                </span>
                <span className="min-w-0">
                  <span className="block truncate font-medium">{fullName(candidate)}</span>
                  <span className="block text-xs text-slate-500">
                    Added {formatDate(candidate.created_at)}
                  </span>
                </span>
              </div>

              <dl className="space-y-2 text-sm">
                <Contact icon={Mail} value={candidate.email} />
                <Contact icon={Phone} value={candidate.phone} />
                <Contact icon={MapPin} value={candidate.location} />
              </dl>

              {candidate.skills?.length ? (
                <div>
                  <h3 className="mb-2 text-xs font-medium tracking-wide text-slate-400 uppercase">
                    Skills
                  </h3>
                  <div className="flex flex-wrap gap-1.5">
                    {candidate.skills.map((skill) => (
                      <span
                        key={skill}
                        className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-700"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}

              {candidate.source ? (
                <p className="text-xs text-slate-500">
                  Source: <span className="text-slate-700">{candidate.source}</span>
                </p>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <FileText className="h-4 w-4" aria-hidden />
                Resumes
              </CardTitle>
            </CardHeader>
            <CardContent>
              {resumes.length === 0 ? (
                <p className="text-sm text-slate-500">No resume on file.</p>
              ) : (
                <ul className="space-y-2 text-sm">
                  {resumes.map((resume) => (
                    <li key={resume.id} className="flex items-center justify-between gap-3">
                      <span className="truncate text-slate-700" title={resume.file_name ?? ""}>
                        {resume.file_name ?? `Resume #${resume.id}`}
                      </span>
                      <span className="shrink-0 text-xs text-slate-400">
                        {formatDate(resume.created_at)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6 lg:col-span-2">
          {candidate.notes ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Notes</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm whitespace-pre-line text-slate-700">{candidate.notes}</p>
              </CardContent>
            </Card>
          ) : null}

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Recommended roles</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {matches.length === 0 ? (
                <p className="text-sm text-slate-500">
                  No role scored above the threshold for this candidate.
                </p>
              ) : (
                matches.slice(0, 5).map((job) => (
                  <div key={job.id} className="rounded-lg border border-slate-200 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <Link href={`/jobs/${job.id}`} className="font-medium hover:underline">
                        {job.title}
                      </Link>
                      <MatchScore score={job.match_score} />
                    </div>
                    <p className="mt-1 text-xs text-slate-500">
                      {[job.department, job.location].filter(Boolean).join(" · ") || "—"}
                    </p>
                    <p className="mt-2 text-sm text-slate-600">{job.match_explanation}</p>
                    <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1">
                      <SubScore label="Skills" score={job.skill_match_score} />
                      <SubScore label="Role" score={job.role_match_score} />
                      <SubScore label="Experience" score={job.experience_match_score} />
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>

          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Applications</CardTitle>
              </CardHeader>
              <CardContent>
                {applications.length === 0 ? (
                  <p className="text-sm text-slate-500">No applications yet.</p>
                ) : (
                  <ul className="divide-y divide-slate-100 text-sm">
                    {applications.map((application) => (
                      <li key={application.id} className="py-2 first:pt-0 last:pb-0">
                        <Link
                          href={`/jobs/${application.job_id}`}
                          className="font-medium hover:underline"
                        >
                          {application.job_title ?? `Job #${application.job_id}`}
                        </Link>
                        <p className="text-xs text-slate-500">
                          {application.status} · applied {formatDate(application.applied_at)}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Saved jobs</CardTitle>
              </CardHeader>
              <CardContent>
                {savedJobs.length === 0 ? (
                  <p className="text-sm text-slate-500">Nothing saved.</p>
                ) : (
                  <ul className="divide-y divide-slate-100 text-sm">
                    {savedJobs.map((saved) => (
                      <li key={saved.id} className="py-2 first:pt-0 last:pb-0">
                        <Link
                          href={`/jobs/${saved.job_id}`}
                          className="font-medium hover:underline"
                        >
                          {saved.job_title ?? `Job #${saved.job_id}`}
                        </Link>
                        <p className="text-xs text-slate-500">
                          Saved {formatDate(saved.saved_at)}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </>
  );
}

function Contact({
  icon: Icon,
  value,
}: {
  icon: typeof Mail;
  value: string | null | undefined;
}) {
  if (!value) return null;
  return (
    <div className="flex items-center gap-2 text-slate-700">
      <Icon className="h-4 w-4 shrink-0 text-slate-400" aria-hidden />
      <span className="truncate">{value}</span>
    </div>
  );
}
