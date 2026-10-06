import { FeedbackTemplatesManager } from "@/components/feedback-templates-manager";
import { ErrorState, PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { listFeedbackTemplates } from "@/lib/data";
import { TEMPLATES_MANAGE, can } from "@/lib/permissions";
import { getUser } from "@/lib/session";

export const dynamic = "force-dynamic";

export const metadata = { title: "Feedback templates · RecruitIQ" };

/** Global feedback templates (Track 2 Phase 4). A job's own are on its page. */
export default async function FeedbackTemplatesPage() {
  const user = await getUser();
  let templates;
  try {
    templates = await listFeedbackTemplates();
  } catch (error) {
    return (
      <>
        <PageHeader title="Feedback templates" />
        <ErrorState
          title="Could not load templates"
          detail={error instanceof ApiError ? error.detail : String(error)}
        />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Feedback templates"
        description="Starting points for interviewers' notes. Offered on every job's feedback form, after that job's own templates."
      />
      <p className="mb-6 max-w-3xl text-xs text-slate-500">
        Templates for one job live on that job&apos;s page. Choosing a template fills the notes box and
        never replaces what the interviewer already wrote.
      </p>
      <Card className="max-w-3xl">
        <CardContent className="p-4">
          <FeedbackTemplatesManager
            templates={templates.filter((t) => t.job_id === null || t.job_id === undefined)}
            editable={can(user?.role ?? null, TEMPLATES_MANAGE)}
          />
        </CardContent>
      </Card>
    </>
  );
}
