import Link from "next/link";

import { EmailComposer } from "@/components/email-composer";
import { StatusLinkControl } from "@/components/status-link-control";
import type { EmailLogEntry, EmailTemplate, StatusLink } from "@/lib/domain";
import { formatDate } from "@/lib/format";

const LOG_LABELS: Record<string, string> = { sent: "Sent", copied: "Copied", failed: "Failed" };

/** Status link, email composer, and email history for one application (ATS Phase E). */
export function ApplicationOutreach({
  applicationId,
  statusLink,
  templates,
  transportConfigured,
  emailLog,
  canSend,
}: {
  applicationId: number;
  statusLink: StatusLink | null;
  templates: EmailTemplate[];
  transportConfigured: boolean;
  emailLog: EmailLogEntry[];
  canSend: boolean;
}) {
  return (
    <div className="space-y-4 border-t border-slate-100 pt-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-medium text-slate-800">Candidate communication</h3>
        <Link
          href={`/applications/${applicationId}/candidate-view`}
          className="text-xs font-medium text-indigo-700 hover:underline"
        >
          See what the candidate sees
        </Link>
      </div>

      {statusLink ? <StatusLinkControl applicationId={applicationId} initial={statusLink} /> : null}

      {templates.length > 0 ? (
        <details className="rounded-md border border-slate-200 p-3">
          <summary className="cursor-pointer text-sm text-slate-700">Email the candidate</summary>
          <div className="mt-3">
            <EmailComposer
              applicationId={applicationId}
              templates={templates.map((t) => ({ key: t.key, name: t.name }))}
              transportConfigured={transportConfigured}
              canSend={canSend}
            />
          </div>
        </details>
      ) : null}

      {emailLog.length > 0 ? (
        <ul className="space-y-1 text-xs text-slate-500">
          {emailLog.slice(0, 5).map((entry) => (
            <li key={entry.id}>
              <span className="font-medium text-slate-700">
                {LOG_LABELS[entry.status] ?? entry.status}
              </span>
              {" · "}
              {entry.subject}
              {" · "}
              {formatDate(entry.created_at)}
              {entry.sent_by_name ? ` · ${entry.sent_by_name}` : ""}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
