import Link from "next/link";
import { Briefcase, TrendingUp, Users } from "lucide-react";

import { ActivityFeed } from "@/components/activity-feed";
import { AttentionList } from "@/components/attention-list";
import { DashboardIntro } from "@/components/dashboard-intro";
import { ErrorState } from "@/components/page-header";
import { StageBadge } from "@/components/stage-badge";
import { StageFunnel } from "@/components/stage-funnel";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { redirectInterviewer } from "@/lib/guards";
import { getDashboard, getSkillsBreakdown, listCandidates, listJobs } from "@/lib/data";
import { fullName } from "@/lib/domain";
import type { Dashboard } from "@/lib/domain";
import { canViewReports } from "@/lib/reports";
import { getUser } from "@/lib/session";

// The dashboard reads live counts; nothing here is safe to prerender.
export const dynamic = "force-dynamic";

function Stat({
  label,
  value,
  icon: Icon,
  tint,
}: {
  label: string;
  value: string | number;
  icon: typeof Users;
  tint: string;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-6">
        <span className={`grid h-11 w-11 shrink-0 place-items-center rounded-lg ${tint}`}>
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
  await redirectInterviewer();
  let candidates;
  let jobs;
  let skills: Record<string, number>;
  let dashboard: Dashboard;
  let user;

  try {
    // In parallel: the dashboard is the first paint a visitor sees, and
    // serialising these is the difference between a snappy load and a
    // noticeable one.
    [candidates, jobs, skills, dashboard, user] = await Promise.all([
      listCandidates({ pageSize: 12 }),
      listJobs(),
      getSkillsBreakdown(),
      getDashboard(),
      getUser(),
    ]);
  } catch (error) {
    return (
      <>
        <DashboardIntro />
        <ErrorState
          title="Could not load the dashboard"
          detail={error instanceof ApiError ? error.detail : String(error)}
        />
      </>
    );
  }

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
      <DashboardIntro />

      {/* An h2, not PageHeader: the intro above owns the page's h1. */}
      <div className="mb-6">
        <h2 className="text-xl font-semibold tracking-tight text-slate-900">Dashboard</h2>
        <p className="mt-1 text-sm text-slate-600">
          Live counts from the database. Every number below is a query over candidates,
          applications, and their stage history, not a fixture.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat
          label="Candidates"
          value={candidates.total}
          icon={Users}
          tint="bg-indigo-50 text-indigo-600"
        />
        <Stat
          label="Open roles"
          value={openJobs}
          icon={Briefcase}
          tint="bg-emerald-50 text-emerald-600"
        />
        <Stat
          label="In interview or later"
          value={dashboard.interviewing_or_later}
          icon={TrendingUp}
          tint="bg-violet-50 text-violet-600"
        />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card className="min-w-0">
          <CardHeader>
            <CardTitle>Pipeline</CardTitle>
          </CardHeader>
          <CardContent>
            <StageFunnel rows={dashboard.funnel} />
          </CardContent>
        </Card>

        <Card className="min-w-0">
          <CardHeader>
            <CardTitle>Needs attention</CardTitle>
          </CardHeader>
          <CardContent>
            <AttentionList
              waiting={dashboard.no_movement}
              waitingTotal={dashboard.no_movement_total}
              pending={dashboard.pending_feedback}
              reportsHref={canViewReports(user?.role) ? "/reports" : undefined}
            />
          </CardContent>
        </Card>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card className="min-w-0">
          <CardHeader>
            <CardTitle>Recent activity</CardTitle>
          </CardHeader>
          <CardContent>
            <ActivityFeed events={dashboard.activity} />
          </CardContent>
        </Card>

        <Card className="min-w-0">
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
                  {candidate.current_position ?? candidate.position_applied ?? "No role listed"}
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
