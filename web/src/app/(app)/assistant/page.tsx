import { AssistantChat } from "@/components/assistant-chat";
import { PageHeader } from "@/components/page-header";
import { redirectInterviewer } from "@/lib/guards";

export const metadata = { title: "AI Assistant · RecruitIQ" };

export default async function AssistantPage() {
  await redirectInterviewer();
  return (
    <>
      <PageHeader
        title="AI Assistant"
        description="Answers come from tool calls against this database, streamed as they run, not from the model's memory."
      />
      <AssistantChat />
    </>
  );
}
