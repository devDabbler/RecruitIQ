"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Copy, Loader2, UserPlus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { STAFF_ROLES, roleLabel } from "@/lib/permissions";

/**
 * Add someone to the team. No email is sent (spec: email arrives in Phase E):
 * the API returns a temporary password once, this shows it once, and the
 * inviter passes it on.
 */
export function TeamInviteForm({ canInviteAdmin }: { canInviteAdmin: boolean }) {
  const router = useRouter();
  const roles = STAFF_ROLES.filter((role) => canInviteAdmin || role !== "admin");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<string>("interviewer");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<{ name: string; email: string; password: string } | null>(null);
  const [copied, setCopied] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    setCopied(false);
    try {
      const response = await fetch("/api/team/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, role }),
      });
      const payload = (await response.json().catch(() => null)) as {
        detail?: string;
        temporary_password?: string;
      } | null;
      if (!response.ok || !payload?.temporary_password) {
        throw new Error(payload?.detail || `Could not add them (${response.status})`);
      }
      setCreated({ name, email, password: payload.temporary_password });
      setName("");
      setEmail("");
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function copy(password: string) {
    try {
      await navigator.clipboard.writeText(password);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Add someone</CardTitle>
        <p className="text-xs text-slate-500">
          They sign in with a temporary password you pass on, then change it in Settings.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={submit} className="space-y-3">
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">Name</span>
            <Input value={name} onChange={(e) => setName(e.target.value)} maxLength={100} required />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">Email</span>
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">Role</span>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="h-9 w-full rounded-md border border-slate-200 bg-white px-2 text-sm"
            >
              {roles.map((r) => (
                <option key={r} value={r}>
                  {roleLabel(r)}
                </option>
              ))}
            </select>
          </label>
          {error ? <p className="text-sm font-medium text-rose-700">{error}</p> : null}
          <Button type="submit" disabled={busy}>
            {busy ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <UserPlus className="mr-2 h-4 w-4" aria-hidden />
            )}
            Add to team
          </Button>
        </form>

        {created ? (
          <div role="status" className="space-y-2 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm">
            <p className="font-medium text-emerald-900">
              {created.name} can now sign in as {created.email}.
            </p>
            <p className="text-emerald-800">Temporary password, shown only this once:</p>
            <div className="flex flex-wrap items-center gap-2">
              <code className="rounded bg-white px-2 py-1 font-mono text-sm text-slate-900">
                {created.password}
              </code>
              <Button type="button" variant="outline" size="sm" onClick={() => copy(created.password)}>
                <Copy className="mr-1.5 h-3.5 w-3.5" aria-hidden />
                {copied ? "Copied" : "Copy"}
              </Button>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
