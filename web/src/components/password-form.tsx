"use client";

import { useState } from "react";
import { KeyRound, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export function PasswordForm() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    if (next !== confirm) {
      setMessage({ ok: false, text: "The new passwords do not match." });
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      const response = await fetch("/api/team/me/password", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_password: current, new_password: next }),
      });
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
      if (!response.ok) throw new Error(payload?.detail || `Could not change it (${response.status})`);
      setCurrent("");
      setNext("");
      setConfirm("");
      setMessage({ ok: true, text: "Password changed." });
    } catch (err) {
      setMessage({ ok: false, text: (err as Error).message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Password</CardTitle>
        <p className="text-xs text-slate-500">At least 12 characters.</p>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-3">
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">Current password</span>
            <Input
              type="password"
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              autoComplete="current-password"
              required
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">New password</span>
            <Input
              type="password"
              value={next}
              onChange={(e) => setNext(e.target.value)}
              autoComplete="new-password"
              minLength={12}
              required
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">New password again</span>
            <Input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              autoComplete="new-password"
              minLength={12}
              required
            />
          </label>
          {message ? (
            <p className={message.ok ? "text-sm text-emerald-700" : "text-sm font-medium text-rose-700"}>
              {message.text}
            </p>
          ) : null}
          <Button type="submit" variant="outline" disabled={busy}>
            {busy ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <KeyRound className="mr-2 h-4 w-4" aria-hidden />
            )}
            Change password
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
