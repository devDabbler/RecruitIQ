"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { STAFF_ROLES, roleLabel } from "@/lib/permissions";

/** Role picker and Remove for one row of the Team page. Admin only (the API checks). */
export function TeamMemberActions({
  member,
  isSelf,
  canChangeRole,
  canRemove,
}: {
  member: { id: string; name: string; role: string };
  isSelf: boolean;
  canChangeRole: boolean;
  canRemove: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(url: string, method: "PUT" | "DELETE", body?: unknown) {
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(url, {
        method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
      if (!response.ok) throw new Error(payload?.detail || `Request failed (${response.status})`);
      setConfirming(false);
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex flex-wrap items-center justify-end gap-2">
        {canChangeRole && !isSelf ? (
          <select
            aria-label={`Role for ${member.name}`}
            value={member.role}
            disabled={busy}
            onChange={(e) => {
              void send(`/api/team/users/${member.id}/role`, "PUT", { role: e.target.value });
            }}
            className="h-8 rounded-md border border-slate-200 bg-white px-2 text-xs"
          >
            {STAFF_ROLES.map((r) => (
              <option key={r} value={r}>
                {roleLabel(r)}
              </option>
            ))}
          </select>
        ) : (
          <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-700">
            {roleLabel(member.role)}
            {isSelf ? " (you)" : ""}
          </span>
        )}
        {canRemove && !isSelf ? (
          confirming ? (
            <>
              <Button
                type="button"
                size="sm"
                disabled={busy}
                onClick={() => send(`/api/team/users/${member.id}`, "DELETE")}
                className="bg-rose-600 text-white hover:bg-rose-700"
              >
                {busy ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden /> : null}
                Remove {member.name}
              </Button>
              <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => setConfirming(false)}>
                Keep
              </Button>
            </>
          ) : (
            <Button type="button" size="sm" variant="outline" onClick={() => setConfirming(true)}>
              Remove
            </Button>
          )
        ) : null}
      </div>
      {error ? <p className="max-w-xs text-right text-xs font-medium text-rose-700">{error}</p> : null}
    </div>
  );
}
