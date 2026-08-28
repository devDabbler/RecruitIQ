"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";

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

  return (
    <div className="flex flex-wrap items-center gap-3">
      <Select
        value={selected}
        onValueChange={(value) =>
          startTransition(() => router.push(`/matching?job=${value}`, { scroll: false }))
        }
      >
        <SelectTrigger className="w-80" aria-label="Job to match against">
          <SelectValue placeholder="Pick a role…" />
        </SelectTrigger>
        <SelectContent>
          {jobs.map((job) => (
            <SelectItem key={job.id} value={String(job.id)}>
              {job.title} · {job.department}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {pending ? <span className="text-sm text-slate-500">Scoring candidates…</span> : null}
    </div>
  );
}
