import Link from "next/link";
import { Suspense } from "react";
import { AlertTriangle, Search } from "lucide-react";

import { JobPicker } from "@/components/job-picker";
import { MatchScore } from "@/components/match-score";
import { EmptyState, ErrorState, PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { getMatchTrace, getScoringPolicy, getSearchTrace, listJobs } from "@/lib/data";
import type { PairTrace, ScoringPolicy, SearchHit } from "@/lib/domain";
import { pct, scoreLadder, similarity } from "@/lib/transparency";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

export const metadata = { title: "Transparency · RecruitIQ" };

function first(value: string | string[] | undefined): string | undefined {
  const raw = Array.isArray(value) ? value[0] : value;
  return raw?.trim() || undefined;
}

/**
 * How every ranking and search is computed, traced from the same code that
 * computes it. Open to every visitor, demo account included: the dataset is
 * fully synthetic, the traces carry no contact details, and a transparency
 * page behind a login would undercut its own point.
 *
 * Two audiences. A developer joining the project gets the whole scoring path
 * on one screen with live numbers instead of reading matching_enhancer.py. A
 * hiring leader gets the answer to "what does your AI look at" as a list that
 * is enforced by a test, not a slide.
 */
export default async function TransparencyPage({ searchParams }: PageProps<"/transparency">) {
  const params = await searchParams;
  const jobParam = first(params.job);
  const candidateParam = first(params.candidate);
  const q = first(params.q);
  const location = first(params.location);

  let policy: ScoringPolicy;
  let jobs;
  try {
    [policy, jobs] = await Promise.all([getScoringPolicy(), listJobs()]);
  } catch (error) {
    return (
      <>
        <PageHeader title="Transparency" />
        <ErrorState
          title="Could not load the scoring policy"
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
  const selected = choices.find((job) => String(job.id) === jobParam) ?? choices[0];

  return (
    <>
      <PageHeader
        title="Transparency"
        description="How every ranking and search in RecruitIQ is computed, read from the same code that computes it. Every candidate here is synthetic, and this page shows less about them than their own profile does."
      />

      <div className="space-y-6">
        <Inputs policy={policy} />
        <HowAScoreIsBuilt policy={policy} />

        <Card>
          <CardHeader>
            <CardTitle>Trace a ranking</CardTitle>
            <p className="text-sm text-slate-500">
              Every candidate scored against one role, including the people the
              Matching screen does not show. Open a row for the arithmetic.
            </p>
          </CardHeader>
          <CardContent>
            {selected ? (
              <>
                <JobPicker
                  jobs={choices}
                  selected={String(selected.id)}
                  basePath="/transparency"
                  label="Trace the ranking for"
                  pendingLabel="Scoring every candidate…"
                />
                <Suspense key={`${selected.id}:${candidateParam ?? ""}`} fallback={<TraceLoading />}>
                  <RankingTrace jobId={selected.id} candidateId={candidateParam} />
                </Suspense>
              </>
            ) : (
              <EmptyState title="No jobs to trace against" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Trace a search</CardTitle>
            <p className="text-sm text-slate-500">
              The assistant&apos;s candidate search, run exactly as the assistant
              runs it: what was embedded, how close each person came, which words
              they matched on, and who was kept out and why.
            </p>
          </CardHeader>
          <CardContent>
            <form method="get" action="/transparency" className="flex flex-wrap items-end gap-3">
              {selected ? <input type="hidden" name="job" value={selected.id} /> : null}
              <label className="block min-w-64 flex-1 text-sm">
                <span className="mb-1 block font-medium text-slate-700">Ask for</span>
                <Input
                  name="q"
                  defaultValue={q ?? ""}
                  placeholder="machine learning engineer with python"
                  aria-label="Search query"
                />
              </label>
              <label className="block w-48 text-sm">
                <span className="mb-1 block font-medium text-slate-700">Place (optional)</span>
                <Input name="location" defaultValue={location ?? ""} placeholder="west coast" />
              </label>
              <Button type="submit" variant="outline">
                <Search className="mr-1.5 h-4 w-4" aria-hidden />
                Trace
              </Button>
            </form>
            {q ? (
              <Suspense key={`${q}:${location ?? ""}`} fallback={<TraceLoading />}>
                <SearchTraceResults q={q} location={location} />
              </Suspense>
            ) : (
              <p className="mt-4 text-sm text-slate-500">
                Enter a request the way a recruiter would type it to the assistant.
              </p>
            )}
          </CardContent>
        </Card>

        <Principles />
        <KnownLimits />
      </div>
    </>
  );
}

// --- what the ranker reads --------------------------------------------------

function Inputs({ policy }: { policy: ScoringPolicy }) {
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <Card>
        <CardHeader>
          <CardTitle>What the ranker reads</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <FieldList heading="From the candidate" fields={policy.candidate_fields_scored} />
          <FieldList heading="From the job" fields={policy.job_fields_scored} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>What it never reads</CardTitle>
          <p className="text-xs text-slate-500">
            A test rewrites every one of these fields and asserts the score does not move.
          </p>
        </CardHeader>
        <CardContent>
          <dl className="space-y-2 text-sm">
            {policy.candidate_fields_never_scored.map((f) => (
              <div key={f.field}>
                <dt className="font-mono text-xs text-slate-700">{f.field}</dt>
                <dd className="text-slate-500">{f.reason}</dd>
              </div>
            ))}
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>What is never collected</CardTitle>
          <p className="text-xs text-slate-500">
            No column, no parser field, nowhere to leak in from.
          </p>
        </CardHeader>
        <CardContent>
          <ul className="space-y-1.5 text-sm text-slate-700">
            {policy.fields_not_collected.map((item) => (
              <li key={item} className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-slate-300" aria-hidden />
                {item}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}

function FieldList({
  heading,
  fields,
}: {
  heading: string;
  fields: { field: string; used_for: string }[];
}) {
  return (
    <div>
      <h3 className="mb-2 text-xs font-medium tracking-wide text-slate-400 uppercase">{heading}</h3>
      <dl className="space-y-2">
        {fields.map((f) => (
          <div key={f.field}>
            <dt className="font-mono text-xs text-slate-700">{f.field}</dt>
            <dd className="text-slate-500">{f.used_for}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

// --- how a score is built ---------------------------------------------------

function HowAScoreIsBuilt({ policy }: { policy: ScoringPolicy }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>How a score is built</CardTitle>
        <p className="text-sm text-slate-500">
          Three components, one weighted blend, two penalties, one threshold.
          The numbers below are read from the ranking code, not typed into this page.
        </p>
      </CardHeader>
      <CardContent className="grid gap-6 lg:grid-cols-2">
        <ol className="space-y-3 text-sm text-slate-700">
          <Step n={1} title="Skill overlap">
            Each job skill is exact (full credit), partial (half credit, a containing
            string within three characters), or missing. Coverage of 80% or more earns a
            10% bonus. If the job or candidate lists no skills, a neutral 30 is used.
          </Step>
          <Step n={2} title="Cross-domain discount">
            When the two titles fall into related but different role families (data
            science versus software engineering, for example) the skill score is
            multiplied by {policy.cross_domain_skill_penalty_factor}. Shared tools do not
            make a different job the same job.
          </Step>
          <Step n={3} title="Role fit">
            Cosine similarity between the job title and the candidate&apos;s current title,
            scaled to 100. The same role family boosts it by 1.3x; a related-but-different
            family caps it at {policy.role_score_caps.moderately_incompatible}; an
            unrelated family caps it at {policy.role_score_caps.highly_incompatible}.
          </Step>
          <Step n={4} title="Seniority">
            Level and years are read from the titles and the job&apos;s stated
            requirements (keywords like &quot;senior&quot; and phrases like &quot;5+ years&quot;).
            Level match counts 70%, years match 30%, with a deduction for a senior person
            on an entry role or the reverse.
          </Step>
          <Step n={5} title="Blend, penalise, threshold">
            The role score picks a weighting tier (right). If the role and skill scores
            are both weak ({policy.final_penalty.condition}) the result is scaled by{" "}
            {policy.final_penalty.multiplier}. Anything under{" "}
            {policy.default_match_threshold} is left off the Matching screen.
          </Step>
        </ol>

        <div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs font-medium tracking-wide text-slate-400 uppercase">
                <th className="pb-2">Tier</th>
                <th className="pb-2">Skills</th>
                <th className="pb-2">Role</th>
                <th className="pb-2">Seniority</th>
                <th className="pb-2">Then scaled by</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {policy.weight_tiers.map((tier) => (
                <tr key={tier.name}>
                  <td className="py-2 pr-3">
                    <span className="font-medium text-slate-800">{tier.label}</span>
                    <span className="block text-xs text-slate-500">{tier.condition}</span>
                  </td>
                  <td className="py-2 tabular-nums">{tier.weights.skill}</td>
                  <td className="py-2 tabular-nums">{tier.weights.role}</td>
                  <td className="py-2 tabular-nums">{tier.weights.experience}</td>
                  <td className="py-2 tabular-nums">{tier.multiplier}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-4 text-xs text-slate-500">
            Semantic search is separate from ranking: it embeds{" "}
            {policy.search_embedded_fields.join(", ")} and drops anything under a cosine
            similarity of {policy.search_relevance_floor}. A hit at or above{" "}
            {policy.search_relevance_bands.strong} is strong. Below that it is moderate
            only when it is at or above {policy.search_relevance_bands.moderate} and a
            specific word from the search appears in the same fields; everything else
            is weak and never reaches the assistant, so an unrelated title cannot be
            dressed up as a partial match.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <li className="flex gap-3">
      <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-indigo-50 text-xs font-semibold text-indigo-700">
        {n}
      </span>
      <span>
        <span className="font-medium text-slate-900">{title}. </span>
        {children}
      </span>
    </li>
  );
}

// --- ranking trace ----------------------------------------------------------

async function RankingTrace({ jobId, candidateId }: { jobId: number; candidateId?: string }) {
  let trace;
  try {
    trace = await getMatchTrace(jobId, { candidateId, limit: 60 });
  } catch (error) {
    return (
      <div className="mt-4">
        <ErrorState
          title="Could not trace this ranking"
          detail={error instanceof ApiError ? error.detail : String(error)}
        />
      </div>
    );
  }

  return (
    <div className="mt-4 space-y-3">
      <p className="text-sm text-slate-600">
        <span className="font-medium text-slate-900">{trace.job.title}</span> reads as{" "}
        {trace.job.level} level, {trace.job.years} years, asking for{" "}
        {trace.job.skills.length ? trace.job.skills.join(", ") : "no listed skills"}.{" "}
        {trace.candidates_scored} candidates scored, {trace.candidates_above_threshold} at or
        above the threshold of {trace.threshold}.
        {candidateId ? (
          <>
            {" "}
            Showing one person.{" "}
            <Link href={`/transparency?job=${jobId}`} className="text-indigo-700 hover:underline">
              Show everyone
            </Link>
          </>
        ) : trace.candidates_scored > trace.traces.length ? (
          <> Showing the top {trace.traces.length}.</>
        ) : null}
      </p>

      {trace.embedding_degraded ? (
        <Degraded>
          The embedding model was unreachable during this pass, so title similarity came
          from placeholder vectors. Role-family rules and skills still applied; the
          similarity numbers below are not meaningful.
        </Degraded>
      ) : null}

      {trace.traces.length === 0 ? (
        <EmptyState title="Nobody to trace" />
      ) : (
        <ol className="space-y-2">
          {trace.traces.map((row) => (
            <TraceRow key={row.candidate_id} trace={row} jobId={jobId} />
          ))}
        </ol>
      )}
    </div>
  );
}

function TraceRow({ trace, jobId }: { trace: PairTrace; jobId: number }) {
  const steps = scoreLadder(trace);
  return (
    <li>
      <details
        className={cn(
          "group rounded-lg border bg-white",
          trace.above_threshold ? "border-slate-200" : "border-dashed border-slate-300",
        )}
      >
        <summary className="flex cursor-pointer list-none flex-wrap items-center gap-3 px-4 py-3 [&::-webkit-details-marker]:hidden">
          <span className="w-8 shrink-0 text-sm font-semibold text-slate-300 tabular-nums">
            {trace.rank}
          </span>
          <span className="min-w-0 flex-1">
            <Link
              href={`/candidates/${trace.candidate_id}`}
              className={cn("font-medium hover:underline", !trace.above_threshold && "text-slate-500")}
            >
              {trace.candidate_name}
            </Link>
            <span className="block truncate text-xs text-slate-500">
              {trace.role.candidate_position || "No current title"}
            </span>
          </span>
          <span className="hidden text-xs text-slate-500 sm:inline">
            skills {pct(trace.skills.score)} · role {pct(trace.role.score)} · seniority{" "}
            {pct(trace.experience.score)}
          </span>
          {trace.above_threshold ? null : (
            <span className="rounded-full border border-slate-200 px-2 py-0.5 text-xs text-slate-500">
              below threshold
            </span>
          )}
          <MatchScore score={trace.match_score} />
        </summary>

        <div className="border-t border-slate-100 px-4 py-4">
          <ol className="space-y-2">
            {steps.map((step, index) => (
              <li key={`${step.label}-${index}`} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-sm">
                <span
                  className={cn(
                    "w-14 shrink-0 text-right font-semibold tabular-nums",
                    step.kind === "penalty" && "text-amber-700",
                    step.kind === "final" && "text-indigo-700",
                  )}
                >
                  {step.value.toFixed(1)}
                </span>
                <span className="w-56 shrink-0 font-medium text-slate-800">{step.label}</span>
                <span className="min-w-0 flex-1 text-slate-600">{step.detail}</span>
              </li>
            ))}
          </ol>
          <p className="mt-3 text-xs text-slate-500">
            Shown to recruiters as: &ldquo;{trace.explanation}&rdquo;
          </p>
          <p className="mt-1 text-xs">
            <Link
              href={`/transparency?job=${jobId}&candidate=${trace.candidate_id}`}
              className="text-indigo-700 hover:underline"
            >
              Link to this trace
            </Link>
          </p>
        </div>
      </details>
    </li>
  );
}

// --- search trace -----------------------------------------------------------

async function SearchTraceResults({ q, location }: { q: string; location?: string }) {
  let trace;
  try {
    trace = await getSearchTrace(q, location);
  } catch (error) {
    return (
      <div className="mt-4">
        <ErrorState
          title="Could not trace this search"
          detail={error instanceof ApiError ? error.detail : String(error)}
        />
      </div>
    );
  }

  return (
    <div className="mt-4 space-y-4 text-sm">
      <p className="text-slate-600">
        Embedded the request as written and compared it against each candidate&apos;s{" "}
        {trace.embedded_fields.join(", ")}.{" "}
        {trace.location_filter ? (
          trace.location_ignored ? (
            <>
              &ldquo;{trace.location_filter}&rdquo; means no place constraint, so no location
              filter was applied.
            </>
          ) : (
            <>
              Place filter &ldquo;{trace.location_filter}&rdquo; became a plain WHERE clause,
              never part of the embedding: <code className="text-xs">{trace.location_patterns.join(" OR ")}</code>.
            </>
          )
        ) : (
          <>No place filter.</>
        )}{" "}
        Floor {trace.relevance_floor}; strong at {trace.relevance_bands.strong}; moderate at{" "}
        {trace.relevance_bands.moderate} plus a word from the search found in{" "}
        {trace.evidence_fields.join(", ")}; weak otherwise, and weak is kept out.
      </p>

      {trace.embedding_degraded ? (
        <Degraded>
          The embedding model was unreachable, so these similarities come from placeholder
          vectors and do not mean anything. The assistant would be equally blind right now,
          which is why it labels results rather than trusting them.
        </Degraded>
      ) : null}

      <HitTable title={`Returned to the assistant (${trace.hits.length})`} hits={trace.hits} />
      {trace.kept_out.length ? (
        <HitTable title={`Kept out (${trace.kept_out.length})`} hits={trace.kept_out} muted />
      ) : null}
    </div>
  );
}

function HitTable({ title, hits, muted = false }: { title: string; hits: SearchHit[]; muted?: boolean }) {
  return (
    <div>
      <h3 className="mb-2 text-xs font-medium tracking-wide text-slate-400 uppercase">{title}</h3>
      {hits.length === 0 ? (
        <p className="text-slate-500">Nobody matched.</p>
      ) : (
        <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
          {hits.map((hit) => (
            <li key={hit.id} className={cn("flex flex-wrap items-start gap-3 px-4 py-3", muted && "text-slate-500")}>
              <span className="min-w-0 flex-1">
                <Link href={`/candidates/${hit.id}`} className="font-medium hover:underline">
                  {hit.name}
                </Link>
                <span className="block text-xs text-slate-500">{hit.location ?? "No location"}</span>
                <span className="mt-1 block text-xs text-slate-500">
                  Embedded: <span className="font-mono">{hit.embedded_text ?? "(no text on file)"}</span>
                </span>
              </span>
              <span className="shrink-0 text-right">
                <span className="block font-semibold tabular-nums">{similarity(hit.similarity)}</span>
                <span className={cn("text-xs", bandClass(hit.relevance))}>{hit.relevance}</span>
                <span className="block text-xs text-slate-500">
                  {hit.matched_on.length ? `matched on ${hit.matched_on.join(", ")}` : "no word in common"}
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function bandClass(band: string): string {
  if (band === "strong") return "text-emerald-700";
  if (band === "moderate") return "text-blue-700";
  return "text-slate-500";
}

// --- shared bits ------------------------------------------------------------

function Degraded({ children }: { children: React.ReactNode }) {
  return (
    <p className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <span>{children}</span>
    </p>
  );
}

function TraceLoading() {
  return (
    <div className="mt-4 space-y-2">
      <Skeleton className="h-4 w-3/4" />
      {[0, 1, 2, 3].map((i) => (
        <Skeleton key={i} className="h-14 w-full rounded-lg" />
      ))}
    </div>
  );
}

function Principles() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Principles this is built on</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="grid gap-4 text-sm text-slate-700 md:grid-cols-2">
          <Principle title="Scores rank. People decide.">
            Nothing in RecruitIQ rejects, advances, or messages a candidate on its own. A
            score orders a list that a recruiter reads, and the recruiter can see why each
            person landed where they did.
          </Principle>
          <Principle title="Every score carries its reasons.">
            The sub-scores and the explanation on the Matching screen are the same
            intermediates shown here, produced by the same function. There is no separate
            &ldquo;explainer&rdquo; that could tell a nicer story than the ranker.
          </Principle>
          <Principle title="No protected characteristics, by construction.">
            The ranker reads two things about a person: their current title and their
            skills. The list of fields it never reads is enforced by a test, and the
            characteristics that matter most are never collected at all.
          </Principle>
          <Principle title="No language model ranks anyone.">
            Ranking is deterministic arithmetic over titles and skills plus one cosine
            similarity between two job titles, and category rules cap what that similarity
            can do. Language models parse resumes and answer chat; they never order people.
          </Principle>
          <Principle title="Weak matches are never shown.">
            A search result is a match only when the similarity is high or a word from the
            search actually appears in the profile, and the assistant is told which words.
            Everyone else is kept out, so the closest available person is never presented
            as a partial match for something unrelated.
          </Principle>
          <Principle title="Say when the model is degraded.">
            If the embedding endpoint is unreachable the system keeps working on placeholder
            vectors, and this page and the API say so rather than passing off placeholder
            similarity as signal.
          </Principle>
          <Principle title="Synthetic data only.">
            Every candidate in the demo dataset is generated. Nothing here describes a real
            person, so nothing here can be used against one.
          </Principle>
        </ul>
      </CardContent>
    </Card>
  );
}

function Principle({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <li>
      <span className="block font-medium text-slate-900">{title}</span>
      <span className="text-slate-600">{children}</span>
    </li>
  );
}

function KnownLimits() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Known limits</CardTitle>
        <p className="text-sm text-slate-500">
          Transparency includes what the scoring gets wrong. These are the ones worth knowing
          before trusting a number.
        </p>
      </CardHeader>
      <CardContent>
        <ul className="space-y-2 text-sm text-slate-700">
          <li>
            <span className="font-medium">Seniority is inferred from titles.</span> A title with
            no level keyword and no years defaults to mid-level, so a &ldquo;Data
            Engineer&rdquo; with fifteen years reads as mid until the parser fills in more.
          </li>
          <li>
            <span className="font-medium">Role families are a fixed keyword list.</span> A title
            outside it (a nurse, a paralegal) gets no family, so neither the boost nor the
            caps apply and the raw title similarity stands alone.
          </li>
          <li>
            <span className="font-medium">Skill matching is string overlap.</span> A synonym is a
            miss: &ldquo;Postgres&rdquo; does not match &ldquo;PostgreSQL&rdquo; unless one
            contains the other.
          </li>
          <li>
            <span className="font-medium">Title similarity comes from an embedding model.</span>{" "}
            Its training data cannot be audited here. The category rules exist to bound how
            far it can move a score, not to make it fair.
          </li>
          <li>
            <span className="font-medium">A shared word is not a fit.</span> A moderate match
            overlaps with the search on the words shown and nothing more; the banding makes
            the assistant honest about that, it does not make the overlap meaningful.
          </li>
        </ul>
      </CardContent>
    </Card>
  );
}
