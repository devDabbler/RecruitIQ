import Link from "next/link";
import { Briefcase, TrendingUp, Users } from "lucide-react";

import { ErrorState, PageHeader } from "@/components/page-header";
import { StageBadge } from "@/components/stage-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { countByStage, getSkillsBreakdown, listCandidates, listJobs } from "@/lib/data";
import { PIPELINE_STAGES, STAGE_LABELS, fullName } from "@/lib/domain";

// The dashboard reads live counts; nothing here is safe to prerender.
export const dynamic = "force-dynamic";

function Stat({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string | number;
  icon: typeof Users;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-6">
        <span className="grid h-11 w-11 shrink-0 place-items-center rounded-lg bg-slate-900/5 text-slate-700">
          <Icon className="h-5 w-5" aria-hidden />
        </span>
        <span>
          <span className="block text-2xl font-semibold tabular-nums">{value}</span>
          <span className="block text-sm text-slate-500">{label}</span>
        </span>
      </CardContent>
    </Card>
  );
}

export default async function DashboardPage() {
  let candidates;
  let jobs;
  let skills: Record<string, number>;
  let stageCounts: Record<string, number>;

  try {
    // In parallel: the dashboard is the first paint a visitor sees, and
    // serialising these is the difference between a snappy load and a
    // noticeable one.
    [candidates, jobs, skills, stageCounts] = await Promise.all([
      listCandidates({ pageSize: 12 }),
      listJobs(),
      getSkillsBreakdown(),
      countByStage(PIPELINE_STAGES),
    ]);
  } catch (error) {
    return (
      <>
        <PageHeader title="Dashboard" />
        <ErrorState
          title="Could not load the dashboard"
          detail={error instanceof ApiError ? error.detail : String(error)}
        />
      </>
    );
  }

  const funnel = PIPELINE_STAGES.map((stage) => ({
    stage,
    count: stageCounts[stage] ?? 0,
  }));
  const largestStage = Math.max(1, ...funnel.map((f) => f.count));

  const topSkills = Object.entries(skills)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 12);
  const maxSkill = Math.max(1, ...topSkills.map(([, n]) => n));

  const openJobs = jobs.results.filter((j) => j.status === "open").length;
  const recent = [...candidates.results]
    .sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""))
    .slice(0, 6);

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Live counts from the seeded database — every number below is a query, not a fixture."
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Candidates" value={candidates.total} icon={Users} />
        <Stat label="Open roles" value={openJobs} icon={Briefcase} />
        <Stat
          label="In interview or later"
          value={funnel
            .filter((f) => ["interviewing", "offered", "hired"].includes(f.stage))
            .reduce((sum, f) => sum + f.count, 0)}
          icon={TrendingUp}
        />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Pipeline</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {funnel.map(({ stage, count }) => (
              <div key={stage} className="flex items-center gap-3">
                <span className="w-24 shrink-0 text-sm text-slate-600">
                  {STAGE_LABELS[stage]}
                </span>
                <span className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                  <span
                    className="block h-full rounded-full bg-slate-800"
                    style={{ width: `${(count / largestStage) * 100}%` }}
                  />
                </span>
                <span className="w-8 text-right text-sm font-medium tabular-nums">{count}</span>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            {/* This widget answered 404 for its entire existence before Phase 3a
                moved the route above /{candidate_id}. */}
            <CardTitle>Top skills</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {topSkills.length === 0 ? (
              <p className="text-sm text-slate-500">No skills recorded yet.</p>
            ) : (
              topSkills.map(([skill, count]) => (
                <div key={skill} className="flex items-center gap-3">
                  <span className="w-36 shrink-0 truncate text-sm text-slate-600" title={skill}>
                    {skill}
                  </span>
                  <span className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                    <span
                      className="block h-full rounded-full bg-blue-500"
                      style={{ width: `${(count / maxSkill) * 100}%` }}
                    />
                  </span>
                  <span className="w-8 text-right text-sm font-medium tabular-nums">{count}</span>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Recently added</CardTitle>
        </CardHeader>
        <CardContent className="divide-y divide-slate-100">
          {recent.map((candidate) => (
            <Link
              key={candidate.id}
              href={`/candidates/${candidate.id}`}
              className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0 hover:bg-slate-50"
            >
              <span className="min-w-0">
                <span className="block truncate font-medium">{fullName(candidate)}</span>
                <span className="block truncate text-sm text-slate-500">
                  {candidate.current_position ?? candidate.position_applied ?? "—"}
                </span>
              </span>
              <StageBadge status={candidate.status} />
            </Link>
          ))}
        </CardContent>
      </Card>
    </>
  );
}
