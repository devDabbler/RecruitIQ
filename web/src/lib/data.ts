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
  CandidateTags,
  Dashboard,
  InterviewEntry,
  InterviewListItem,
  InterviewScope,
  Job,
  JobList,
  JobMatch,
  JobPipeline,
  MatchTrace,
  Note,
  Profile,
  Report,
  ResumeSummary,
  SavedJob,
  ScoringPolicy,
  SearchTrace,
  SkillsBreakdown,
  StageDefaults,
  TeamMember,
  UploadPolicy,
} from "./domain";
import { getToken } from "./session";

export interface CandidateQuery {
  keyword?: string;
  status?: string;
  jobId?: string;
  page?: number;
  pageSize?: number;
}

export async function listCandidates({
  keyword,
  status,
  jobId,
  page = 1,
  pageSize = 25,
}: CandidateQuery = {}): Promise<CandidateSearch> {
  return apiFetch<CandidateSearch>("/api/candidates/", {
    token: await getToken(),
    query: { keyword, status, job_id: jobId, page, page_size: pageSize },
  });
}

/** The API caps `page_size` at 100, and asking for more is a 422. */
export const MAX_PAGE_SIZE = 100;

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

// --- ATS Phase B: team, interviews, feedback --------------------------------

/** Everyone on the team. Emails are null for roles that cannot invite. */
export async function listTeam(): Promise<TeamMember[]> {
  const result = await apiFetch<{ members: TeamMember[] }>("/api/team/users", {
    token: await getToken(),
  });
  return result.members;
}

export async function getMyProfile(): Promise<Profile | null> {
  return apiFetchOptional<Profile>("/api/team/me", { token: await getToken() });
}

export async function listInterviews(scope: InterviewScope): Promise<InterviewListItem[]> {
  const result = await apiFetch<{ items: InterviewListItem[] }>("/api/interviews", {
    token: await getToken(),
    query: { scope },
  });
  return result.items;
}

export async function getApplicationInterviews(applicationId: number): Promise<InterviewEntry[]> {
  return (
    (await apiFetchOptional<InterviewEntry[]>(`/api/applications/${applicationId}/interviews`, {
      token: await getToken(),
    })) ?? []
  );
}

export async function getDefaultInterviewers(jobId: number): Promise<StageDefaults[] | null> {
  const result = await apiFetchOptional<{ stages: StageDefaults[] }>(
    `/api/jobs/${jobId}/default-interviewers`,
    { token: await getToken() },
  );
  return result?.stages ?? null;
}

/** A candidate's notes thread, newest first (ATS Phase C). */
export async function getCandidateNotes(candidateId: string): Promise<Note[]> {
  return (
    (await apiFetchOptional<Note[]>(`/api/candidates/${encodeURIComponent(candidateId)}/notes`, {
      token: await getToken(),
    })) ?? []
  );
}

/** A candidate's tags, alphabetical. */
export async function getCandidateTags(candidateId: string): Promise<string[]> {
  const result = await apiFetchOptional<CandidateTags>(
    `/api/candidates/${encodeURIComponent(candidateId)}/tags`,
    { token: await getToken() },
  );
  return result?.tags ?? [];
}

/** The dashboard's pipeline cards (ATS Phase D): funnel, attention list, activity. */
export async function getDashboard(): Promise<Dashboard> {
  return apiFetch<Dashboard>("/api/reports/dashboard", { token: await getToken() });
}

/**
 * Everything on the Reports page, for every job or one. Throws ApiError 403
 * for an interviewer; the page checks the role before calling.
 */
export async function getReport(jobId?: number): Promise<Report> {
  return apiFetch<Report>("/api/reports/summary", {
    token: await getToken(),
    query: { job_id: jobId },
  });
}
