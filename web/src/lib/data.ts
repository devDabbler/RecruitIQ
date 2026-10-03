/**
 * Server-side data access for the eight screens.
 *
 * One function per thing a screen needs. Server Components call these directly
 * rather than going through a Next route handler — the Next docs are explicit
 * that fetching a route handler from a Server Component adds an HTTP hop for
 * nothing (`backend-for-frontend.md`, "Caveats").
 *
 * Each one attaches the session token from the cookie, so the API sees the
 * demo user and its read-only role.
 */
import "server-only";

import { apiFetch, apiFetchOptional } from "./api";
import type {
  Application,
  ApplicationDetail,
  Candidate,
  CandidateMatch,
  CandidateSearch,
  Job,
  JobList,
  JobMatch,
  JobPipeline,
  MatchTrace,
  ResumeSummary,
  SavedJob,
  ScoringPolicy,
  SearchTrace,
  SkillsBreakdown,
  UploadPolicy,
} from "./domain";
import { getToken } from "./session";

export interface CandidateQuery {
  keyword?: string;
  status?: string;
  page?: number;
  pageSize?: number;
}

export async function listCandidates({
  keyword,
  status,
  page = 1,
  pageSize = 25,
}: CandidateQuery = {}): Promise<CandidateSearch> {
  return apiFetch<CandidateSearch>("/api/candidates/", {
    token: await getToken(),
    query: { keyword, status, page, page_size: pageSize },
  });
}

/** The API caps `page_size` at 100, and asking for more is a 422. */
export const MAX_PAGE_SIZE = 100;

/**
 * How many candidates sit at each funnel stage.
 *
 * One filtered query per stage, reading `total` rather than counting rows.
 * Counting a single fetched page instead would silently under-report the moment
 * the database outgrows one page — the funnel would look right in the demo and
 * be wrong in production, which is the worst combination.
 */
export async function countByStage(stages: readonly string[]): Promise<Record<string, number>> {
  const token = await getToken();
  const counts = await Promise.all(
    stages.map(async (status) => {
      const page = await apiFetch<CandidateSearch>("/api/candidates/", {
        token,
        query: { status, page: 1, page_size: 1 },
      });
      return [status, page.total] as const;
    }),
  );
  return Object.fromEntries(counts);
}

export async function getCandidate(id: string): Promise<Candidate | null> {
  return apiFetchOptional<Candidate>(`/api/candidates/${encodeURIComponent(id)}`, {
    token: await getToken(),
  });
}

export async function getSkillsBreakdown(): Promise<SkillsBreakdown> {
  return apiFetch<SkillsBreakdown>("/api/candidates/skills_breakdown", {
    token: await getToken(),
  });
}

export async function listJobs(page = 1, pageSize = 50): Promise<JobList> {
  return apiFetch<JobList>("/api/jobs/", {
    token: await getToken(),
    query: { page, page_size: pageSize },
  });
}

export async function getJob(id: number | string): Promise<Job | null> {
  return apiFetchOptional<Job>(`/api/jobs/${id}`, { token: await getToken() });
}

/**
 * Rank candidates against a job.
 *
 * Uses /api/enhanced-matching/*, not /api/search/match_*. The latter returns
 * free-form agent output with no `response_model`; guessing one would risk the
 * silent truncation the golden tests exist to catch. enhanced-matching is fully
 * modelled and a superset, so the typed route wins.
 */
export async function matchCandidatesForJob(
  jobId: number,
  minScore = 0,
): Promise<CandidateMatch[]> {
  const result = await apiFetch<{ candidates: CandidateMatch[] }>(
    "/api/enhanced-matching/match-candidates",
    {
      method: "POST",
      token: await getToken(),
      body: { job_ids: [jobId], min_score: minScore },
    },
  );
  return result.candidates ?? [];
}

/** The mirror image: rank open roles against one candidate. */
export async function matchJobsForCandidate(
  candidateId: string,
  minScore = 0,
): Promise<JobMatch[]> {
  const result = await apiFetch<{ jobs: JobMatch[] }>("/api/enhanced-matching/match-jobs", {
    method: "POST",
    token: await getToken(),
    body: { candidate_id: candidateId, min_score: minScore },
  });
  return result.jobs ?? [];
}

export async function getCandidateResumes(candidateId: string): Promise<ResumeSummary[]> {
  const result = await apiFetchOptional<{ resumes: ResumeSummary[] }>(
    `/api/candidates/${encodeURIComponent(candidateId)}/resumes`,
    { token: await getToken() },
  );
  return result?.resumes ?? [];
}

export async function getCandidateApplications(candidateId: string): Promise<Application[]> {
  return (
    (await apiFetchOptional<Application[]>(
      `/api/jobs/applications/${encodeURIComponent(candidateId)}`,
      { token: await getToken() },
    )) ?? []
  );
}

export async function getCandidateSavedJobs(candidateId: string): Promise<SavedJob[]> {
  return (
    (await apiFetchOptional<SavedJob[]>(
      `/api/jobs/saved/${encodeURIComponent(candidateId)}`,
      { token: await getToken() },
    )) ?? []
  );
}

/** The stages of one job and who is at each (ATS Phase A). */
export async function getJobPipeline(jobId: number | string): Promise<JobPipeline | null> {
  return apiFetchOptional<JobPipeline>(`/api/jobs/${jobId}/pipeline`, {
    token: await getToken(),
  });
}

/** One application with its full stage timeline. */
export async function getApplication(id: number | string): Promise<ApplicationDetail | null> {
  return apiFetchOptional<ApplicationDetail>(`/api/applications/${id}`, {
    token: await getToken(),
  });
}

// --- admin-only scoring transparency ---------------------------------------
//
// These three throw an ApiError with status 401/403 for anyone but an admin;
// the /transparency page redirects to sign-in before it ever calls them.

export async function getScoringPolicy(): Promise<ScoringPolicy> {
  return apiFetch<ScoringPolicy>("/api/transparency/policy", { token: await getToken() });
}

export async function getUploadPolicy(): Promise<UploadPolicy> {
  return apiFetch<UploadPolicy>("/api/transparency/upload-policy", { token: await getToken() });
}

/**
 * Every candidate scored against one job, below-threshold ones included.
 * Same cost as the Matching screen (it is the same scoring pass), so it is
 * streamed behind a Suspense boundary like that screen's results.
 */
export async function getMatchTrace(
  jobId: number,
  options: { candidateId?: string; limit?: number } = {},
): Promise<MatchTrace> {
  return apiFetch<MatchTrace>("/api/transparency/match-trace", {
    token: await getToken(),
    query: { job_id: jobId, candidate_id: options.candidateId, limit: options.limit },
  });
}

export async function getSearchTrace(q: string, location?: string): Promise<SearchTrace> {
  return apiFetch<SearchTrace>("/api/transparency/search-trace", {
    token: await getToken(),
    query: { q, location },
  });
}
