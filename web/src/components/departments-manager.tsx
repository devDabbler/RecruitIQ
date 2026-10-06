"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Check, Loader2, Pencil, Plus, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { Department } from "@/lib/domain";

/**
 * The department list jobs choose from (Track 2 Phase 3).
 *
 * Everyone on the Team page sees it; only an admin gets Add, Rename, and
 * Turn off (the API checks). A rename moves every job in that department
 * with it; a turned-off department stays on its existing jobs but is not
 * offered for new ones.
 */
export function DepartmentsManager({
  departments,
  canManage,
}: {
  departments: Department[];
  canManage: boolean;
}) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function send(url: string, method: "POST" | "PUT", body: unknown): Promise<unknown> {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const response = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = (await response.json().catch(() => null)) as { detail?: unknown } | null;
      if (!response.ok) {
        const detail = typeof payload?.detail === "string" ? payload.detail : null;
        throw new Error(detail || `Request failed (${response.status})`);
      }
      router.refresh();
      return payload;
    } catch (err) {
      setError((err as Error).message);
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function add(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim() || busy) return;
    if (await send("/api/departments", "POST", { name: name.trim() })) setName("");
  }

  async function rename(department: Department) {
    if (!draft.trim() || busy) return;
    if (draft.trim() === department.name) {
      setEditing(null);
      return;
    }
    const result = (await send(`/api/departments/${department.id}`, "PUT", {
      name: draft.trim(),
    })) as {
      jobs_renamed?: number;
    } | null;
    if (result) {
      setEditing(null);
      const moved = result.jobs_renamed ?? 0;
      if (moved > 0)
        setNotice(`Renamed, and moved ${moved} ${moved === 1 ? "job" : "jobs"} with it.`);
    }
  }

  const active = departments.filter((d) => d.active).length;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Departments</CardTitle>
        <p className="text-xs text-slate-500">
          Jobs choose from this list, so reports never split one team across two spellings.
          {canManage ? " Renaming a department moves its jobs with it." : null}
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {departments.length === 0 ? (
          <p className="text-sm text-slate-500">
            No departments yet.
            {canManage ? " Add the first one below." : " An admin adds them here."}
          </p>
        ) : (
          <ul
            className="divide-y divide-slate-100 text-sm"
            aria-label={`${active} active departments`}
          >
            {departments.map((department) => (
              <li
                key={department.id}
                className="flex flex-wrap items-center justify-between gap-2 py-2"
              >
                {editing === department.id ? (
                  <form
                    className="flex flex-1 items-center gap-2"
                    onSubmit={(e) => {
                      e.preventDefault();
                      void rename(department);
                    }}
                  >
                    <Input
                      value={draft}
                      onChange={(e) => setDraft(e.target.value)}
                      maxLength={100}
                      aria-label={`New name for ${department.name}`}
                      className="h-8"
                      autoFocus
                    />
                    <Button type="submit" size="sm" disabled={busy} aria-label="Save name">
                      <Check className="h-3.5 w-3.5" aria-hidden />
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={busy}
                      onClick={() => setEditing(null)}
                      aria-label="Cancel rename"
                    >
                      <X className="h-3.5 w-3.5" aria-hidden />
                    </Button>
                  </form>
                ) : (
                  <>
                    <span className="min-w-0">
                      <span
                        className={
                          department.active
                            ? "font-medium text-slate-900"
                            : "text-slate-400 line-through"
                        }
                      >
                        {department.name}
                      </span>
                      <span className="ml-2 text-xs text-slate-500">
                        {department.job_count} {department.job_count === 1 ? "job" : "jobs"}
                        {department.active ? "" : " · turned off"}
                      </span>
                    </span>
                    {canManage ? (
                      <span className="flex items-center gap-1">
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          disabled={busy}
                          onClick={() => {
                            setEditing(department.id);
                            setDraft(department.name);
                            setError(null);
                          }}
                          aria-label={`Rename ${department.name}`}
                        >
                          <Pencil className="h-3.5 w-3.5" aria-hidden />
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={busy}
                          onClick={() =>
                            void send(`/api/departments/${department.id}`, "PUT", {
                              active: !department.active,
                            })
                          }
                        >
                          {department.active ? "Turn off" : "Turn on"}
                        </Button>
                      </span>
                    ) : null}
                  </>
                )}
              </li>
            ))}
          </ul>
        )}

        {canManage ? (
          <form onSubmit={add} className="flex items-center gap-2">
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="New department"
              aria-label="New department"
              maxLength={100}
            />
            <Button type="submit" disabled={busy || !name.trim()}>
              {busy ? (
                <Loader2 className="mr-1.5 h-4 w-4 animate-spin" aria-hidden />
              ) : (
                <Plus className="mr-1.5 h-4 w-4" aria-hidden />
              )}
              Add
            </Button>
          </form>
        ) : null}
        {notice ? <p className="text-xs text-emerald-700">{notice}</p> : null}
        {error ? <p className="text-sm font-medium text-rose-700">{error}</p> : null}
      </CardContent>
    </Card>
  );
}
