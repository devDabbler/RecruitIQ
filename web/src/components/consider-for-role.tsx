"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Plus } from "lucide-react";

import { SourceSelect } from "@/components/source-select";
import { Button } from "@/components/ui/button";
import { describeError } from "@/lib/intake";

/**
 * Put this person on another open job's pipeline.
 *
 * Creates a second application, not a second candidate: one person, one
 * profile, many pipelines (spec decision 2). Only open jobs they have not
 * applied to are offered.
 */
export function ConsiderForRole({
  candidateId,
  jobs,
}: {
  candidateId: string;
  jobs: { id: number; title: string; department: string }[];
}) {
  const router = useRouter();
  const [jobId, setJobId] = useState("");
  // Usually an internal move; a recruiter can say a referral or agency sent them.
  const [source, setSource] = useState("internal");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!jobId || busy) return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`/api/jobs/${jobId}/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ candidate_id: candidateId, source }),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: unknown } | null;
        throw new Error(describeError(payload?.detail, response.status));
      }
      setJobId("");
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (jobs.length === 0) return null;

  return (
    <form
      onSubmit={submit}
      className="flex flex-wrap items-center gap-2 rounded-lg border border-dashed border-slate-300 bg-white p-3 text-sm"
    >
      <label htmlFor="consider-job" className="font-medium text-slate-700">
        Consider for another role
      </label>
      <select
        id="consider-job"
        value={jobId}
        onChange={(e) => setJobId(e.target.value)}
        className="min-w-0 flex-1 rounded-md border border-slate-200 bg-white px-2 py-1.5 text-sm text-slate-700"
      >
        <option value="">Choose a job</option>
        {jobs.map((job) => (
          <option key={job.id} value={job.id}>
            {job.title} ({job.department})
          </option>
        ))}
      </select>
      <SourceSelect value={source} onChange={setSource} className="py-1.5" />
      <Button type="submit" size="sm" disabled={!jobId || busy}>
        {busy ? (
          <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
        ) : (
          <Plus className="mr-2 h-4 w-4" aria-hidden />
        )}
        Add to pipeline
      </Button>
      {error ? <p className="w-full text-sm font-medium text-rose-700">{error}</p> : null}
    </form>
  );
}
