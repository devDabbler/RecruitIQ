import { AssignInterviewer } from "@/components/assign-interviewer";
import { FeedbackForm } from "@/components/feedback-form";
import type { ApplicationDetail, InterviewEntry, TeamMember } from "@/lib/domain";
import { formatDate } from "@/lib/format";
import { INTERVIEW_STATE_LABELS, RECOMMENDATION_LABELS, memberName } from "@/lib/interviews";

/**
 * Who interviews this candidate for this job, and what they thought
 * (ATS Phase B). Rendered inside the application's timeline card.
 *
 * The API decides what each viewer may read: a colleague's feedback arrives
 * as `feedback_hidden` until the viewer has submitted their own.
 */
export function InterviewPanel({
  application,
  interviews,
  team,
  viewerId,
  canAssign,
}: {
  application: ApplicationDetail;
  interviews: InterviewEntry[];
  team: TeamMember[];
  viewerId: string | null;
  canAssign: boolean;
}) {
  const rounds = application.stages
    .filter((s) => s.kind === "round" && s.enabled && s.status !== "skipped")
    .map((s) => ({ key: s.key, name: s.name }));

  return (
    <section id={`interviews-${application.id}`} className="space-y-3 border-t border-slate-100 pt-4">
      <h3 className="text-sm font-medium text-slate-800">Interviews and feedback</h3>
      {interviews.length === 0 ? (
        <p className="text-sm text-slate-500">No interviewers assigned yet.</p>
      ) : (
        <ul className="space-y-3">
          {interviews.map((interview) => (
            <li key={interview.id} className="rounded-md border border-slate-200 p-3 text-sm">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="font-medium text-slate-800">
                  {interview.interviewer_name}{" "}
                  <span className="text-xs font-normal text-slate-500">{interview.stage_name}</span>
                </span>
                <span className="text-xs text-slate-500">{INTERVIEW_STATE_LABELS[interview.state]}</span>
              </div>
              {interview.feedback ? (
                <div className="mt-2 space-y-1">
                  <p className="text-slate-700">
                    {interview.feedback.rating} of 5 ·{" "}
                    {RECOMMENDATION_LABELS[interview.feedback.recommendation] ??
                      interview.feedback.recommendation}
                  </p>
                  {interview.feedback.notes ? (
                    <p className="whitespace-pre-line text-slate-600">{interview.feedback.notes}</p>
                  ) : null}
                  <p className="text-xs text-slate-400">
                    Submitted {formatDate(interview.feedback.submitted_at)}
                  </p>
                </div>
              ) : interview.feedback_hidden ? (
                <p className="mt-2 text-xs text-slate-500">
                  Feedback submitted. You will see it after you submit your own.
                </p>
              ) : interview.interviewer_id === viewerId && interview.state === "waiting" ? (
                <FeedbackForm interviewId={interview.id} stageName={interview.stage_name} />
              ) : null}
            </li>
          ))}
        </ul>
      )}
      {canAssign && application.status === "active" ? (
        <AssignInterviewer
          applicationId={application.id}
          stages={rounds}
          team={team.map((m) => ({ id: m.id, name: memberName(m) }))}
          defaultStage={application.current_stage_key ?? undefined}
        />
      ) : null}
    </section>
  );
}
