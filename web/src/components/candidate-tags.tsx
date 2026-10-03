"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { MAX_TAGS_PER_CANDIDATE, describeError, normalizeTag } from "@/lib/intake";

/**
 * Tag chips, with add and remove for writers.
 *
 * Shows what a typed tag will be saved as before it is sent, because the
 * server normalizes ("Relocation OK" becomes relocation-ok).
 */
export function CandidateTags({
  candidateId,
  tags,
  writable,
}: {
  candidateId: string;
  tags: string[];
  writable: boolean;
}) {
  const router = useRouter();
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const preview = draft.trim() ? normalizeTag(draft) : "";
  const base = `/api/candidates/${encodeURIComponent(candidateId)}/tags`;

  async function send(method: "POST" | "DELETE", tag: string) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const response =
        method === "POST"
          ? await fetch(base, {
              method,
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ tag }),
            })
          : await fetch(`${base}/${encodeURIComponent(tag)}`, { method });
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: unknown } | null;
        throw new Error(describeError(payload?.detail, response.status));
      }
      if (method === "POST") setDraft("");
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!writable && tags.length === 0) return null;

  return (
    <div>
      <h3 className="mb-2 text-xs font-medium tracking-wide text-slate-400 uppercase">Tags</h3>
      <div className="flex flex-wrap gap-1.5">
        {tags.length === 0 ? (
          <span className="text-xs text-slate-400">No tags yet.</span>
        ) : (
          tags.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center gap-1 rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-xs text-indigo-700"
            >
              {tag}
              {writable ? (
                <button
                  type="button"
                  onClick={() => send("DELETE", tag)}
                  disabled={busy}
                  aria-label={`Remove tag ${tag}`}
                  className="rounded-full text-indigo-400 hover:text-indigo-700"
                >
                  <X className="h-3 w-3" aria-hidden />
                </button>
              ) : null}
            </span>
          ))
        )}
      </div>
      {writable && tags.length < MAX_TAGS_PER_CANDIDATE ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (preview) send("POST", draft);
          }}
          className="mt-2 flex gap-2"
        >
          <Input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Add a tag"
            aria-label="New tag"
            maxLength={80}
            className="h-8 text-sm"
          />
          <Button type="submit" size="sm" variant="outline" disabled={!preview || busy}>
            Add
          </Button>
        </form>
      ) : null}
      {writable && draft.trim() && preview !== draft.trim() ? (
        <p className="mt-1 text-xs text-slate-500">
          {preview ? `Saved as ${preview}` : "Use at least one letter or number."}
        </p>
      ) : null}
      {error ? <p className="mt-1 text-xs font-medium text-rose-700">{error}</p> : null}
    </div>
  );
}
