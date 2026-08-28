import { AssistantChat } from "@/components/assistant-chat";
import { PageHeader } from "@/components/page-header";

export const metadata = { title: "AI Assistant — RecruitIQ" };

export default function AssistantPage() {
  return (
    <>
      <PageHeader
        title="AI Assistant"
        description="Answers come from tool calls against this database, streamed as they run — not from the model's memory."
      />
      <AssistantChat />
    </>
  );
}
