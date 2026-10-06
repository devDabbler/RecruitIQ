"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, UserPlus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { SourceSelect } from "@/components/source-select";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { describeError } from "@/lib/intake";
import { DEFAULT_SOURCE } from "@/lib/sources";

/**
 * Add a person by hand: name, email, how they found us (Track 2 Phase 3),
 * and optionally the job they are for.
 *
 * Choosing a job puts them at Resume submitted on it in the same request,
 * so the new profile opens with its pipeline already started.
 */
export function AddCandidatePanel({
  jobs,
}: {
  jobs: { id: number; title: string; department: string }[];
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [jobId, setJobId] = useState("");
  const [source, setSource] = useState<string>(DEFAULT_SOURCE);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch("/api/candidates", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          first_name: firstName.trim(),
          last_name: lastName.trim(),
          email: email.trim(),
          job_id: jobId ? Number(jobId) : null,
          source,
        }),
      });
      const payload = (await response.json().catch(() => null)) as {
        id?: string;
        detail?: unknown;
      } | null;
      if (!response.ok || !payload?.id) {
        throw new Error(describeError(payload?.detail, response.status));
      }
      router.push(`/candidates/${payload.id}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <div className="mb-4 flex justify-end">
        <Button type="button" onClick={() => setOpen(true)}>
          <UserPlus className="mr-2 h-4 w-4" aria-hidden />
          Add candidate
        </Button>
      </div>
    );
  }

  return (
    <Card className="mb-4">
      <CardContent className="p-4">
        <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Input
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
            placeholder="First name"
            aria-label="First name"
            required
          />
          <Input
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
            placeholder="Last name"
            aria-label="Last name"
            required
          />
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Email"
            aria-label="Email"
            required
          />
          <select
            value={jobId}
            onChange={(e) => setJobId(e.target.value)}
            aria-label="Job"
            className="rounded-md border border-slate-200 bg-white px-2 py-2 text-sm text-slate-700"
          >
            <option value="">No job yet</option>
            {jobs.map((job) => (
              <option key={job.id} value={job.id}>
                {job.title} ({job.department})
              </option>
            ))}
          </select>
          <label className="flex items-center gap-2 text-sm text-slate-600 sm:col-span-2 lg:col-span-4">
            How did they find us?
            <SourceSelect id="add-source" value={source} onChange={setSource} />
          </label>
          <div className="flex flex-wrap items-center gap-2 sm:col-span-2 lg:col-span-4">
            <Button type="submit" disabled={busy}>
              {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden /> : null}
              {jobId ? "Add and start pipeline" : "Add candidate"}
            </Button>
            <Button type="button" variant="outline" disabled={busy} onClick={() => setOpen(false)}>
              Cancel
            </Button>
            {error ? <p className="text-sm font-medium text-rose-700">{error}</p> : null}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
