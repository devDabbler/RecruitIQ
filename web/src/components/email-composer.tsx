"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Copy, Loader2, Mail, Send } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { EmailPreview } from "@/lib/domain";
import { composeClipboardText, remainingPlaceholders, sendState } from "@/lib/email-composer";

/**
 * Pick a template, review and edit the filled-in text, then send it or copy
 * it (ATS Phase E). Copying is always possible; when the account may send
 * and nothing is left unfilled, a copy is also written to the email history.
 */
export function EmailComposer({
  applicationId,
  templates,
  transportConfigured,
  canSend,
}: {
  applicationId: number;
  templates: { key: string; name: string }[];
  transportConfigured: boolean;
  canSend: boolean;
}) {
  const router = useRouter();
  const [templateKey, setTemplateKey] = useState(templates[0]?.key ?? "");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [toAddress, setToAddress] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState<"load" | "send" | "copy" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const remaining = remainingPlaceholders(subject, body);
  const state = sendState({ canSend, transportConfigured, remaining });

  async function load() {
    setBusy("load");
    setError(null);
    setNotice(null);
    try {
      const response = await fetch(
        `/api/applications/${applicationId}/emails/preview?template_key=${encodeURIComponent(templateKey)}`,
      );
      const payload = (await response.json().catch(() => null)) as
        | (EmailPreview & { detail?: string })
        | null;
      if (!response.ok || !payload) {
        throw new Error(payload?.detail || `Could not load the template (${response.status})`);
      }
      setSubject(payload.subject);
      setBody(payload.body);
      setToAddress(payload.to_address ?? null);
      setLoaded(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function record(mode: "send" | "copied") {
    const response = await fetch(`/api/applications/${applicationId}/emails`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ template_key: templateKey || null, subject, body, mode }),
    });
    const payload = (await response.json().catch(() => null)) as { detail?: unknown } | null;
    if (!response.ok) {
      throw new Error(
        typeof payload?.detail === "string"
          ? payload.detail
          : `Could not record the email (${response.status})`,
      );
    }
  }

  async function send() {
    setBusy("send");
    setError(null);
    try {
      await record("send");
      setNotice(`Sent to ${toAddress ?? "the candidate"}.`);
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function copy() {
    setBusy("copy");
    setError(null);
    try {
      await navigator.clipboard.writeText(composeClipboardText(subject, body));
      if (canSend && remaining.length === 0) {
        await record("copied");
        setNotice("Copied, and noted in the email history.");
        router.refresh();
      } else {
        setNotice("Copied.");
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor={`template-${applicationId}`} className="text-xs font-medium text-slate-600">
          Template
        </label>
        <select
          id={`template-${applicationId}`}
          value={templateKey}
          onChange={(e) => setTemplateKey(e.target.value)}
          className="h-8 rounded-md border border-slate-200 bg-white px-2 text-sm"
        >
          {templates.map((template) => (
            <option key={template.key} value={template.key}>
              {template.name}
            </option>
          ))}
        </select>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={load}
          disabled={busy !== null || !templateKey}
        >
          {busy === "load" ? (
            <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" aria-hidden />
          ) : (
            <Mail className="mr-1 h-3.5 w-3.5" aria-hidden />
          )}
          Use template
        </Button>
      </div>

      {loaded ? (
        <>
          {toAddress ? <p className="text-xs text-slate-500">To: {toAddress}</p> : null}
          <Input value={subject} onChange={(e) => setSubject(e.target.value)} aria-label="Subject" />
          <Textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={10}
            aria-label="Message"
          />
          {state.reason ? <p className="text-xs text-amber-700">{state.reason}</p> : null}
          <div className="flex flex-wrap gap-2">
            {canSend && transportConfigured ? (
              <Button type="button" onClick={send} disabled={!state.allowed || busy !== null}>
                {busy === "send" ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
                ) : (
                  <Send className="mr-2 h-4 w-4" aria-hidden />
                )}
                Send
              </Button>
            ) : null}
            <Button type="button" variant="outline" onClick={copy} disabled={busy !== null}>
              <Copy className="mr-2 h-4 w-4" aria-hidden />
              Copy text
            </Button>
          </div>
        </>
      ) : null}

      {notice ? <p className="text-xs font-medium text-emerald-700">{notice}</p> : null}
      {error ? <p className="text-xs font-medium text-rose-700">{error}</p> : null}
    </div>
  );
}
