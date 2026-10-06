import Link from "next/link";
import { Download } from "lucide-react";

import { AddCandidatePanel } from "@/components/add-candidate-panel";
import { CandidateFilters } from "@/components/candidate-filters";
import { type BulkContext, CandidateTable, type FitColumn } from "@/components/candidate-table";
import { EmptyState, ErrorState, PageHeader } from "@/components/page-header";
import { buttonVariants } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { getJobPipeline, listCandidates, listJobs } from "@/lib/data";
import type { CandidateSearch } from "@/lib/domain";
import { fitQuery, fitSortFrom } from "@/lib/fit";
import { applicationsByCandidate, exportHref } from "@/lib/intake";
import { canWrite } from "@/lib/session";

export const dynamic = "force-dynamic";

const PAGE_SIZE = 25;

export default async function CandidatesPage({ searchParams }: PageProps<"/candidates">) {
  const params = await searchParams;
  const keyword = first(params.q);
  const status = first(params.status);
  const jobId = first(params.job);
  // A hand-edited `?page=abc` should land on page 1, not send NaN to the API.
  const page = Math.max(1, Number(first(params.page)) || 1);
  // Track 2 Phase 2: a job's applicants are ranked by fit, best first.
  const fitSort = jobId ? fitSortFrom(first(params.sort)) : null;

  const [writable, jobList] = await Promise.all([canWrite(), listJobs().catch(() => null)]);
  const jobs = (jobList?.results ?? [])
    .map(({ id, title, department, status: jobStatus }) => ({
      id,
      title,
      department,
      status: jobStatus,
    }))
    .sort((a, b) => a.title.localeCompare(b.title));
  const exportLink = (
    <a
      href={exportHref({ keyword, status, jobId })}
      className={buttonVariants({ variant: "outline" })}
      download
    >
      <Download className="mr-1.5 h-4 w-4" aria-hidden />
      Export CSV
    </a>
  );

  let data: CandidateSearch;
  try {
    data = await listCandidates({
      keyword,
      status,
      jobId,
      page,
      pageSize: PAGE_SIZE,
      ...(fitSort ? fitQuery(fitSort) : {}),
    });
  } catch (error) {
    return (
      <>
        <PageHeader title="Candidates" />
        <ErrorState
          title="Could not load candidates"
          detail={error instanceof ApiError ? error.detail : String(error)}
        />
      </>
    );
  }

  // Bulk moves need applications, and an application belongs to one job, so
  // the checkboxes only appear once the list is filtered to a job.
  let bulk: BulkContext | null = null;
  if (writable && jobId) {
    const pipeline = await getJobPipeline(jobId).catch(() => null);
    const job = jobs.find((j) => String(j.id) === jobId);
    if (pipeline && job) {
      bulk = { jobTitle: job.title, applications: applicationsByCandidate(pipeline) };
    }
  }

  const fit: FitColumn | null = fitSort
    ? {
        sort: fitSort,
        toggleHref: listHref(params, { sort: fitSort === "best" ? "worst" : null, page: null }),
      }
    : null;

  const lastPage = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
  const from = data.total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const to = Math.min(page * PAGE_SIZE, data.total);

  return (
    <>
      <PageHeader
        title="Candidates"
        description={data.total === 1 ? "1 candidate" : `${data.total} candidates in the pipeline`}
        actions={exportLink}
      />

      {writable ? <AddCandidatePanel jobs={jobs.filter((j) => j.status === "open")} /> : null}

      <CandidateFilters
        initialKeyword={keyword ?? ""}
        initialStatus={status ?? ""}
        initialJob={jobId ?? ""}
        jobs={jobs}
      />

      {data.results.length === 0 ? (
        <EmptyState
          title="No candidates match those filters"
          detail="Clear the search box, pick a different stage, or choose All jobs."
        />
      ) : (
        <CandidateTable candidates={data.results} bulk={bulk} fit={fit} />
      )}

      {data.total > PAGE_SIZE ? (
        <div className="mt-4 flex items-center justify-between text-sm text-slate-600">
          <span>
            Showing {from} to {to} of {data.total}
          </span>
          <span className="flex gap-2">
            <PageLink params={params} page={page - 1} disabled={page <= 1}>
              Previous
            </PageLink>
            <PageLink params={params} page={page + 1} disabled={page >= lastPage}>
              Next
            </PageLink>
          </span>
        </div>
      ) : null}
    </>
  );
}

/**
 * This page's URL with some params changed (null removes one). Rebuilt from
 * the incoming params so paging and sorting preserve the active search, stage
 * and job filters instead of silently resetting them.
 */
function listHref(
  params: Record<string, string | string[] | undefined>,
  changes: Record<string, string | null>,
): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    const single = first(value);
    if (!(key in changes) && single) query.set(key, single);
  }
  for (const [key, value] of Object.entries(changes)) {
    if (value !== null) query.set(key, value);
  }
  const text = query.toString();
  return text ? `/candidates?${text}` : "/candidates";
}

/** Next hands repeated query params through as arrays; take the first. */
function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function PageLink({
  params,
  page,
  disabled,
  children,
}: {
  params: Record<string, string | string[] | undefined>;
  page: number;
  disabled: boolean;
  children: React.ReactNode;
}) {
  if (disabled) {
    return (
      <span className="rounded-md border border-slate-200 px-3 py-1.5 text-slate-300">
        {children}
      </span>
    );
  }

  return (
    <Link
      href={listHref(params, { page: String(page) })}
      className="rounded-md border border-slate-200 bg-white px-3 py-1.5 font-medium hover:border-slate-300"
    >
      {children}
    </Link>
  );
}
