"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Plus, Save, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { FeedbackTemplate } from "@/lib/domain";

async function send(url: string, method: "POST" | "PUT" | "DELETE", body?: unknown): Promise<void> {
  const response = await fetch(url, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (response.ok) return;
  const payload = (await response.json().catch(() => null)) as { detail?: unknown } | null;
  throw new Error(
    typeof payload?.detail === "string" ? payload.detail : `Could not save (${response.status})`,
  );
}

/**
 * Feedback templates (Track 2 Phase 4): starting text interviewers can drop
 * into their notes. Global ones live on the Feedback templates page; a job's
 * own on the job page (`jobId`). Read-only for roles without templates.manage.
 */
export function FeedbackTemplatesManager({
  templates,
  jobId = null,
  editable,
}: {
  templates: FeedbackTemplate[];
  jobId?: number | null;
  editable: boolean;
}) {
  return (
    <div className="space-y-4">
      {templates.length === 0 ? (
        <p className="text-sm text-slate-500">
          {jobId ? "No templates for this job yet." : "No templates yet."}
        </p>
      ) : (
        <ul className="space-y-3">
          {templates.map((template) => (
            <li key={template.id}>
              {editable ? (
                <TemplateRow template={template} />
              ) : (
                <div className="rounded-md border border-slate-200 p-3 text-sm">
                  <p className="font-medium text-slate-800">{template.name}</p>
                  <p className="mt-1 whitespace-pre-line text-slate-600">{template.body}</p>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      {editable ? <NewTemplate jobId={jobId} /> : null}
    </div>
  );
}

function TemplateRow({ template }: { template: FeedbackTemplate }) {
  const router = useRouter();
  const [name, setName] = useState(template.name);
  const [body, setBody] = useState(template.body);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      await action();
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2 rounded-md border border-slate-200 p-3 text-sm">
      <Input value={name} onChange={(e) => setName(e.target.value)} aria-label="Template name" maxLength={80} />
      <Textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        rows={5}
        maxLength={5000}
        aria-label={`${template.name} text`}
      />
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          size="sm"
          disabled={busy}
          onClick={() =>
            run(async () => {
              await send(`/api/feedback-templates/${template.id}`, "PUT", { name, body });
              setSaved(true);
            })
          }
        >
          {busy ? (
            <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden />
          ) : (
            <Save className="mr-1.5 h-3.5 w-3.5" aria-hidden />
          )}
          Save
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={busy}
          onClick={() => {
            if (window.confirm(`Delete the template "${template.name}"?`)) {
              void run(() => send(`/api/feedback-templates/${template.id}`, "DELETE"));
            }
          }}
        >
          <Trash2 className="mr-1.5 h-3.5 w-3.5" aria-hidden />
          Delete
        </Button>
        {saved ? <span className="text-xs text-emerald-700">Saved.</span> : null}
        {error ? <span className="text-xs font-medium text-rose-700">{error}</span> : null}
      </div>
    </div>
  );
}

function NewTemplate({ jobId }: { jobId: number | null }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) {
    return (
      <Button type="button" size="sm" variant="outline" onClick={() => setOpen(true)}>
        <Plus className="mr-1.5 h-3.5 w-3.5" aria-hidden />
        Add a template
      </Button>
    );
  }

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !body.trim()) {
      setError("Give the template a name and some text.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await send("/api/feedback-templates", "POST", { name, body, job_id: jobId });
      setName("");
      setBody("");
      setOpen(false);
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={add} className="space-y-2 rounded-md border border-dashed border-slate-300 p-3 text-sm">
      <Input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Name, for example Technical interview"
        aria-label="New template name"
        maxLength={80}
      />
      <Textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        rows={5}
        maxLength={5000}
        placeholder={"Strengths:\n\nConcerns:\n\nEvidence:"}
        aria-label="New template text"
      />
      <div className="flex items-center gap-2">
        <Button type="submit" size="sm" disabled={busy}>
          {busy ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden /> : null}
          Add template
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={() => setOpen(false)}>
          Cancel
        </Button>
        {error ? <span className="text-xs font-medium text-rose-700">{error}</span> : null}
      </div>
    </form>
  );
}
