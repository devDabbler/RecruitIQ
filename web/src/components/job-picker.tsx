"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { Loader2 } from "lucide-react";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

/**
 * Choose which job to rank candidates against.
 *
 * The selection lives in the URL, so the ranking is a Server Component render
 * against the live API rather than client state — and `/matching?job=3` is a
 * link someone can paste into Slack.
 */
export function JobPicker({
  jobs,
  selected,
}: {
  jobs: { id: number; title: string; department: string }[];
  selected: string;
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  // Base UI's Select.Value renders the raw value ("82") unless told otherwise;
  // resolve it to the job title the recruiter actually recognises.
  const selectedJob = jobs.find((job) => String(job.id) === selected);

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
      <label
        htmlFor="job-picker"
        className="text-sm font-medium text-slate-700"
      >
        Rank candidates for
      </label>
      <Select
        value={selected}
        onValueChange={(value) =>
          startTransition(() => router.push(`/matching?job=${value}`, { scroll: false }))
        }
      >
        <SelectTrigger
          id="job-picker"
          className="h-10 w-full max-w-md bg-white"
          aria-label="Job to match against"
        >
          <SelectValue>
            {selectedJob ? (
              <span className="truncate">
                {selectedJob.title}
                <span className="text-slate-400"> · {selectedJob.department}</span>
              </span>
            ) : (
              "Pick a role…"
            )}
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          {jobs.map((job) => (
            <SelectItem key={job.id} value={String(job.id)}>
              <span className="flex min-w-0 flex-col items-start text-left">
                <span className="truncate font-medium">{job.title}</span>
                <span className="truncate text-xs text-slate-500">{job.department}</span>
              </span>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {pending ? (
        <span className="flex items-center gap-1.5 text-sm text-slate-500">
          <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
          Scoring candidates…
        </span>
      ) : null}
    </div>
  );
}
