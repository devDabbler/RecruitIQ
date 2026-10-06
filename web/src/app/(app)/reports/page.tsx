import Link from "next/link";
import { Download } from "lucide-react";

import { JobPicker } from "@/components/job-picker";
import { EmptyState, ErrorState, PageHeader } from "@/components/page-header";
import { StageFunnel } from "@/components/stage-funnel";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ApiError } from "@/lib/api";
import { getReport, listJobs } from "@/lib/data";
import type { Report } from "@/lib/domain";
import { formatDate } from "@/lib/format";
import { canViewReports, daysLabel, exportHref, formatDays } from "@/lib/reports";
import { sourceLabel } from "@/lib/sources";
import { getUser } from "@/lib/session";

export const dynamic = "force-dynamic";

export const metadata = { title: "Reports · RecruitIQ" };

const QUERY_NOTE =
  "Every number on this page is a query over applications and their stage history, run when " +
  "the page loads. Nothing is estimated, sampled, or projected.";

function first(value: string | string[] | undefined): string | undefined {
  const raw = Array.isArray(value) ? value[0] : value;
  return raw?.trim() || undefined;
}

/**
 * Funnel, time in stage, outcomes, sources, and the no-movement list, for all
 * jobs or one. Open to the hiring roles and to the read-only demo; an
 * interviewer is told plainly instead of seeing an error.
 */
export default async function ReportsPage({ searchParams }: PageProps<"/reports">) {
  const params = await searchParams;
  const jobParam = first(params.job);
  const jobId = jobParam && /^\d+$/.test(jobParam) ? Number(jobParam) : undefined;

  const user = await getUser();
  if (user && !canViewReports(user.role)) {
    return (
      <>
        <PageHeader title="Reports" />
        <EmptyState
          title="Reports are not available for your role"
          detail="Your assigned candidates and the feedback you owe are on the Interviews page."
        />
      </>
    );
  }

  let report: Report;
  let jobs;
  try {
    [report, jobs] = await Promise.all([getReport(jobId), listJobs()]);
  } catch (error) {
    if (error instanceof ApiError && error.isNotFound) {
      return (
        <>
          <PageHeader title="Reports" />
          <EmptyState title="That job does not exist" detail="Pick another job, or show all jobs." />
        </>
      );
    }
    return (
      <>
        <PageHeader title="Reports" />
        <ErrorState
          title="Could not load reports"
          detail={error instanceof ApiError ? error.detail : String(error)}
        />
      </>
    );
  }

  const [thisQuarter, lastQuarter] = report.quarters;

  return (
    <>
      <PageHeader
        title="Reports"
        description={QUERY_NOTE}
        actions={
          <a href={exportHref(jobId)} className={buttonVariants({ variant: "outline" })}>
            <Download className="mr-1.5 h-4 w-4" aria-hidden />
            Export candidates (CSV)
          </a>
        }
      />

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <JobPicker
          jobs={jobs.results.map((job) => ({
            id: job.id,
            title: job.title,
            department: job.department ?? "",
          }))}
          selected={jobId ? String(jobId) : ""}
          basePath="/reports"
          label="Filter by job"
          pendingLabel="Running the queries..."
        />
        {jobId ? (
          <Link href="/reports" className="text-sm text-indigo-600 hover:underline">
            Show all jobs
          </Link>
        ) : null}
      </div>

      <p className="mb-4 text-sm text-slate-600">
        {report.job_title ?? "All jobs"}: {report.total_applications} applications.
      </p>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="min-w-0">
          <CardHeader>
            <CardTitle>Funnel</CardTitle>
          </CardHeader>
          <CardContent>
            <StageFunnel rows={report.funnel} showShare />
          </CardContent>
        </Card>

        <Card className="min-w-0">
          <CardHeader>
            <CardTitle>Hires and rejections</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Quarter</TableHead>
                  <TableHead className="text-right">Hires</TableHead>
                  <TableHead className="text-right">Rejections</TableHead>
                  <TableHead className="text-right">Offers declined</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {[thisQuarter, lastQuarter].map((quarter, index) => (
                  <TableRow key={quarter.label}>
                    <TableCell>
                      {quarter.label}
                      <span className="ml-2 text-xs text-slate-400">
                        {index === 0 ? "this quarter" : "last quarter"}
                      </span>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{quarter.hires}</TableCell>
                    <TableCell className="text-right tabular-nums">{quarter.rejections}</TableCell>
                    <TableCell className="text-right tabular-nums">{quarter.offers_declined}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card className="min-w-0">
          <CardHeader>
            <CardTitle>Time in stage</CardTitle>
          </CardHeader>
          <CardContent>
            {report.time_in_stage.length === 0 ? (
              <p className="text-sm text-slate-500">
                No stage has been completed yet, so there is no time to measure.
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Stage</TableHead>
                    <TableHead className="text-right">Median</TableHead>
                    <TableHead className="text-right">Completed</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {report.time_in_stage.map((row) => (
                    <TableRow key={row.key}>
                      <TableCell>{row.name}</TableCell>
                      <TableCell className="text-right tabular-nums">{formatDays(row.median_days)}</TableCell>
                      <TableCell className="text-right tabular-nums">{row.completed}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
            <p className="mt-3 text-xs text-slate-500">
              Median days from entering a stage to leaving it, over applications that finished
              the stage. Stages nobody has finished are left out.
            </p>
          </CardContent>
        </Card>

        <Card className="min-w-0">
          <CardHeader>
            <CardTitle>Where applicants come from</CardTitle>
          </CardHeader>
          <CardContent>
            {report.source_mix.length === 0 ? (
              <p className="text-sm text-slate-500">No applications yet.</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Source</TableHead>
                    <TableHead className="text-right">Applications</TableHead>
                    <TableHead className="text-right">Hired</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {report.source_mix.map((row) => (
                    <TableRow key={row.source}>
                      <TableCell>{row.label || sourceLabel(row.source)}</TableCell>
                      <TableCell className="text-right tabular-nums">{row.applications}</TableCell>
                      <TableCell className="text-right tabular-nums">{row.hired}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <Card className="min-w-0">
          <CardHeader>
            <CardTitle>By department</CardTitle>
          </CardHeader>
          <CardContent>
            {report.department_mix.length === 0 ? (
              <p className="text-sm text-slate-500">No applications yet.</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Department</TableHead>
                    <TableHead className="text-right">Jobs</TableHead>
                    <TableHead className="text-right">Applications</TableHead>
                    <TableHead className="text-right">Hired</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {report.department_mix.map((row) => (
                    <TableRow key={row.department}>
                      <TableCell>{row.department}</TableCell>
                      <TableCell className="text-right tabular-nums">{row.jobs}</TableCell>
                      <TableCell className="text-right tabular-nums">{row.applications}</TableCell>
                      <TableCell className="text-right tabular-nums">{row.hired}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
            <p className="mt-3 text-xs text-slate-500">
              Departments come from the fixed list on the Team page, so one team is never split
              across two spellings.
            </p>
          </CardContent>
        </Card>
      </div>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>No movement in 7+ days</CardTitle>
        </CardHeader>
        <CardContent>
          {report.no_movement.length === 0 ? (
            <p className="text-sm text-slate-500">Every active candidate moved in the last 7 days.</p>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Candidate</TableHead>
                    <TableHead>Job</TableHead>
                    <TableHead>Stage</TableHead>
                    <TableHead>Since</TableHead>
                    <TableHead className="text-right">Waiting</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {report.no_movement.map((row) => (
                    <TableRow key={row.application_id}>
                      <TableCell>
                        <Link href={`/candidates/${row.candidate_id}`} className="font-medium hover:underline">
                          {row.candidate_name}
                        </Link>
                      </TableCell>
                      <TableCell>
                        <Link href={`/jobs/${row.job_id}`} className="hover:underline">
                          {row.job_title}
                        </Link>
                      </TableCell>
                      <TableCell>{row.stage_name}</TableCell>
                      <TableCell>{formatDate(row.since)}</TableCell>
                      <TableCell className="text-right tabular-nums">{daysLabel(row.days_waiting)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              {report.no_movement_total > report.no_movement.length ? (
                <p className="mt-3 text-xs text-slate-500">
                  Showing the {report.no_movement.length} longest waits of {report.no_movement_total}.
                </p>
              ) : null}
            </>
          )}
        </CardContent>
      </Card>

      <p className="mt-6 text-xs text-slate-400">Queried {formatDate(report.generated_at)}.</p>
    </>
  );
}
