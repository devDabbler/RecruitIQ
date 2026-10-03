"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

const TIMEZONES = [
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Phoenix",
  "America/Los_Angeles",
  "America/Anchorage",
  "Pacific/Honolulu",
  "Europe/London",
  "Europe/Berlin",
  "Asia/Kolkata",
  "Asia/Singapore",
  "Australia/Sydney",
  "UTC",
];

export function SettingsForm({
  name: initialName,
  timezone: initialTimezone,
  email,
  roleText,
}: {
  name: string;
  timezone: string;
  email: string;
  roleText: string;
}) {
  const router = useRouter();
  const [name, setName] = useState(initialName);
  const [timezone, setTimezone] = useState(initialTimezone);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setMessage(null);
    try {
      const response = await fetch("/api/team/me", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, timezone: timezone || null }),
      });
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
      if (!response.ok) throw new Error(payload?.detail || `Could not save (${response.status})`);
      setMessage({ ok: true, text: "Saved." });
      router.refresh();
    } catch (err) {
      setMessage({ ok: false, text: (err as Error).message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Profile</CardTitle>
        <p className="text-xs text-slate-500">
          {email} · {roleText}
        </p>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-3">
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">Name</span>
            <Input value={name} onChange={(e) => setName(e.target.value)} maxLength={100} required />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">Time zone</span>
            <select
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              className="h-9 w-full rounded-md border border-slate-200 bg-white px-2 text-sm"
            >
              <option value="">Not set</option>
              {TIMEZONES.map((zone) => (
                <option key={zone} value={zone}>
                  {zone.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </label>
          {message ? (
            <p className={message.ok ? "text-sm text-emerald-700" : "text-sm font-medium text-rose-700"}>
              {message.text}
            </p>
          ) : null}
          <Button type="submit" disabled={busy}>
            {busy ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <Save className="mr-2 h-4 w-4" aria-hidden />
            )}
            Save
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
