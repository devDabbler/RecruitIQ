"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { EmailTemplate } from "@/lib/domain";
import { unknownPlaceholders } from "@/lib/email-composer";

/** One email template: editable for template managers, read-only for everyone else. */
export function TemplateEditor({
  template,
  placeholders,
  editable,
}: {
  template: EmailTemplate;
  placeholders: string[];
  editable: boolean;
}) {
  const router = useRouter();
  const [name, setName] = useState(template.name);
  const [subject, setSubject] = useState(template.subject);
  const [body, setBody] = useState(template.body);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  if (!editable) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{template.name}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p className="font-medium text-slate-800">{template.subject}</p>
          <p className="whitespace-pre-line text-slate-600">{template.body}</p>
        </CardContent>
      </Card>
    );
  }

  async function save() {
    const unknown = unknownPlaceholders(`${subject}\n${body}`, placeholders);
    if (unknown.length > 0) {
      setError(`Unknown placeholder {{${unknown[0]}}}.`);
      return;
    }
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const response = await fetch(`/api/email-templates/${template.key}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, subject, body }),
      });
      const payload = (await response.json().catch(() => null)) as { detail?: unknown } | null;
      if (!response.ok) {
        throw new Error(
          typeof payload?.detail === "string" ? payload.detail : `Could not save (${response.status})`,
        );
      }
      setSaved(true);
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardContent className="space-y-3 p-6 text-sm">
        <Input value={name} onChange={(e) => setName(e.target.value)} aria-label="Template name" />
        <Input value={subject} onChange={(e) => setSubject(e.target.value)} aria-label="Subject" />
        <Textarea value={body} onChange={(e) => setBody(e.target.value)} rows={10} aria-label="Body" />
        <div className="flex items-center gap-3">
          <Button type="button" onClick={save} disabled={busy}>
            {busy ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <Save className="mr-2 h-4 w-4" aria-hidden />
            )}
            Save
          </Button>
          {saved ? <span className="text-xs text-emerald-700">Saved.</span> : null}
          {error ? <span className="text-xs font-medium text-rose-700">{error}</span> : null}
        </div>
      </CardContent>
    </Card>
  );
}
