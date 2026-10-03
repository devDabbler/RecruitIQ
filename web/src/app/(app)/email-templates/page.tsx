import { PageHeader } from "@/components/page-header";
import { TemplateEditor } from "@/components/template-editor";
import { Card, CardContent } from "@/components/ui/card";
import { getEmailTemplates } from "@/lib/data";
import { TEMPLATES_MANAGE, can } from "@/lib/permissions";
import { getUser } from "@/lib/session";

export const dynamic = "force-dynamic";

/** The four candidate email templates (ATS Phase E). */
export default async function EmailTemplatesPage() {
  const [data, user] = await Promise.all([getEmailTemplates(), getUser()]);
  const editable = can(user?.role ?? null, TEMPLATES_MANAGE);

  return (
    <>
      <PageHeader
        title="Email templates"
        description="Starting points for candidate email. Each one is filled in from the application and can be edited before it goes out."
      />
      <Card className="mb-4">
        <CardContent className="p-4 text-sm text-slate-700">
          {data.transport_configured
            ? "Sending is turned on. Messages go out from the address configured on the server."
            : "No mail server is configured, so the composer offers the finished text to copy into your own inbox."}
        </CardContent>
      </Card>
      <p className="mb-6 text-xs text-slate-500">
        Placeholders you can use: {data.placeholders.map((p) => `{{${p}}}`).join(", ")}
      </p>
      <div className="max-w-3xl space-y-6">
        {data.templates.map((template) => (
          <TemplateEditor
            key={template.key}
            template={template}
            placeholders={data.placeholders}
            editable={editable}
          />
        ))}
      </div>
    </>
  );
}
