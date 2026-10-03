"use client";

import { useState } from "react";
import { Check, Copy, Link2, Loader2, RefreshCw, Unlink } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { StatusLink } from "@/lib/domain";

/**
 * Create, copy, replace, or turn off a candidate's status link (ATS Phase E).
 *
 * Shows the relative path, not an absolute URL, so server and client render
 * the same text; the absolute URL is built only when copying.
 */
export function StatusLinkControl({
  applicationId,
  initial,
}: {
  applicationId: number;
  initial: StatusLink;
}) {
  const [link, setLink] = useState<StatusLink>(initial);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function call(method: "POST" | "DELETE") {
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`/api/applications/${applicationId}/status-link`, { method });
      const payload = (await response.json().catch(() => null)) as
        | (StatusLink & { detail?: string })
        | null;
      if (!response.ok || !payload) {
        throw new Error(payload?.detail || `Could not update the link (${response.status})`);
      }
      setLink(payload);
      setCopied(false);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function copy() {
    if (!link.path) return;
    try {
      await navigator.clipboard.writeText(new URL(link.path, window.location.origin).toString());
      setCopied(true);
    } catch {
      setError("Could not copy. Select the link and copy it by hand.");
    }
  }

  const icon = "mr-1 h-3.5 w-3.5";
  return (
    <div className="space-y-2 text-sm">
      <p className="text-xs text-slate-500">
        Anyone with the status link sees the candidate&apos;s first name, the job, and the stage
        list. Nothing else.
      </p>
      {link.active && link.path ? (
        <div className="flex flex-wrap items-center gap-2">
          <a
            href={link.path}
            target="_blank"
            rel="noreferrer"
            className="max-w-full truncate font-mono text-xs text-indigo-700 hover:underline"
          >
            {link.path}
          </a>
          <Button type="button" size="sm" variant="outline" onClick={copy} disabled={busy}>
            {copied ? <Check className={icon} aria-hidden /> : <Copy className={icon} aria-hidden />}
            {copied ? "Copied" : "Copy link"}
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => call("POST")}
            disabled={busy}
          >
            <RefreshCw className={icon} aria-hidden />
            Replace
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => call("DELETE")}
            disabled={busy}
          >
            <Unlink className={icon} aria-hidden />
            Turn off
          </Button>
        </div>
      ) : (
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => call("POST")}
          disabled={busy}
        >
          {busy ? (
            <Loader2 className={`${icon} animate-spin`} aria-hidden />
          ) : (
            <Link2 className={icon} aria-hidden />
          )}
          Create status link
        </Button>
      )}
      {link.active ? (
        <p className="text-xs text-slate-400">
          Replacing the link stops the old one working immediately.
        </p>
      ) : null}
      {error ? <p className="text-xs font-medium text-rose-700">{error}</p> : null}
    </div>
  );
}
