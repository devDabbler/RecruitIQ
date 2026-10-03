import { ErrorState, PageHeader } from "@/components/page-header";
import { TeamInviteForm } from "@/components/team-invite-form";
import { TeamMemberActions } from "@/components/team-member-actions";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { listTeam } from "@/lib/data";
import { formatDate } from "@/lib/format";
import { redirectInterviewer } from "@/lib/guards";
import { memberName } from "@/lib/interviews";
import { DELETE_RECORDS, USERS_CHANGE_ROLE, USERS_INVITE, can, roleLabel } from "@/lib/permissions";
import { getUser } from "@/lib/session";

export const dynamic = "force-dynamic";

export const metadata = { title: "Team · RecruitIQ" };

const ROLE_GUIDE = [
  ["admin", "Everything, including roles and removing people."],
  ["hiring_manager", "Jobs, candidates, moving candidates, and adding people."],
  ["hiring_team", "Candidates, and moving them through the pipeline."],
  ["interviewer", "Their own interviews and feedback. Match scores appear after they submit feedback."],
] as const;

export default async function TeamPage() {
  await redirectInterviewer();
  const user = await getUser();

  let members;
  try {
    members = await listTeam();
  } catch (error) {
    return (
      <>
        <PageHeader title="Team" />
        <ErrorState
          title="Could not load the team"
          detail={error instanceof ApiError ? error.detail : String(error)}
        />
      </>
    );
  }

  const role = user?.role;
  const canInvite = can(role, USERS_INVITE);
  const canChangeRole = can(role, USERS_CHANGE_ROLE);
  const canRemove = can(role, DELETE_RECORDS);

  return (
    <>
      <PageHeader title="Team" description="Who can sign in, and what each role can do." />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">
              {members.length} {members.length === 1 ? "person" : "people"}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {members.length === 0 ? (
              <p className="text-sm text-slate-500">Nobody yet besides the demo account.</p>
            ) : (
              <ul className="divide-y divide-slate-100 text-sm">
                {members.map((member) => (
                  <li
                    key={member.id}
                    className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 last:pb-0"
                  >
                    <span className="min-w-0">
                      <span className="block truncate font-medium text-slate-900">
                        {memberName(member)}
                      </span>
                      <span className="block truncate text-xs text-slate-500">
                        {member.email ? `${member.email} · ` : ""}joined {formatDate(member.created_at)}
                      </span>
                    </span>
                    {canChangeRole || canRemove ? (
                      <TeamMemberActions
                        member={{ id: member.id, name: memberName(member), role: member.role }}
                        isSelf={member.id === user?.id}
                        canChangeRole={canChangeRole}
                        canRemove={canRemove}
                      />
                    ) : (
                      <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-700">
                        {roleLabel(member.role)}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <div className="space-y-6">
          {canInvite ? (
            <TeamInviteForm canInviteAdmin={role === "admin"} />
          ) : (
            <Card>
              <CardContent className="p-6 text-sm text-slate-500">
                Hiring managers and administrators can add people to the team.
              </CardContent>
            </Card>
          )}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">What each role can do</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="space-y-3 text-sm">
                {ROLE_GUIDE.map(([key, text]) => (
                  <div key={key}>
                    <dt className="font-medium text-slate-800">{roleLabel(key)}</dt>
                    <dd className="text-slate-500">{text}</dd>
                  </div>
                ))}
              </dl>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
