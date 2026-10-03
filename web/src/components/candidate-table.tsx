"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Loader2, X } from "lucide-react";

import { StageBadge } from "@/components/stage-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { type BulkTransitionResult, type Candidate, fullName, initials } from "@/lib/domain";
import { type ActiveApplication, bulkSummary, describeError } from "@/lib/intake";

/** Present when the list is filtered to one job: who can be moved, and where they are. */
export interface BulkContext {
  jobTitle: string;
  applications: Record<string, ActiveApplication>;
}

interface Outcome {
  summary: string;
  failures: { name: string; detail: string }[];
}

/**
 * The candidates table. With a job filter it gains checkboxes and a bar to
 * advance or reject the selection; every candidate who could not be moved is
 * listed by name with the reason, because the server moves the rest anyway.
 */
export function CandidateTable({
  candidates,
  bulk,
}: {
  candidates: Candidate[];
  bulk: BulkContext | null;
}) {
  const router = useRouter();
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [confirmReject, setConfirmReject] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<"advance" | "reject" | null>(null);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectable = useMemo(
    () =>
      bulk
        ? candidates.flatMap((c) =>
            bulk.applications[c.id] ? [bulk.applications[c.id].applicationId] : [],
          )
        : [],
    [bulk, candidates],
  );
  const allSelected = selectable.length > 0 && selectable.every((id) => selected.has(id));

  function toggle(id: number) {
    setSelected((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function run(action: "advance" | "reject") {
    if (busy || selected.size === 0) return;
    setBusy(action);
    setError(null);
    setOutcome(null);
    try {
      const response = await fetch(`/api/applications/bulk/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          application_ids: [...selected],
          note: action === "reject" ? note.trim() || null : null,
        }),
      });
      const payload = (await response.json().catch(() => null)) as
        | (BulkTransitionResult & { detail?: unknown })
        | null;
      if (!response.ok || !payload?.results) {
        throw new Error(describeError(payload?.detail, response.status));
      }
      setOutcome({
        summary: bulkSummary(action, payload.succeeded, payload.failed),
        failures: payload.results
          .filter((r) => !r.ok)
          .map((r) => ({
            name: r.candidate_name ?? `Application ${r.application_id}`,
            detail: r.detail ?? "Not moved.",
          })),
      });
      setSelected(new Set());
      setConfirmReject(false);
      setNote("");
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-3">
      {bulk ? (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-white p-3 text-sm">
          <span className="text-slate-600">
            {selected.size === 0
              ? `Select candidates in ${bulk.jobTitle} to move them together.`
              : `${selected.size} selected in ${bulk.jobTitle}`}
          </span>
          <span className="ml-auto flex gap-2">
            <Button
              type="button"
              size="sm"
              onClick={() => run("advance")}
              disabled={selected.size === 0 || busy !== null}
            >
              {busy === "advance" ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
              ) : (
                <ArrowRight className="mr-2 h-4 w-4" aria-hidden />
              )}
              Advance
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => setConfirmReject(true)}
              disabled={selected.size === 0 || busy !== null}
            >
              <X className="mr-2 h-4 w-4" aria-hidden />
              Reject
            </Button>
          </span>
          {confirmReject ? (
            <div
              role="alertdialog"
              aria-label="Reject the selected candidates?"
              className="w-full space-y-2 rounded-md border border-rose-200 bg-rose-50 p-3"
            >
              <p className="font-medium text-rose-900">
                Reject {selected.size} {selected.size === 1 ? "candidate" : "candidates"} in{" "}
                {bulk.jobTitle}? Each application ends at its current stage.
              </p>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={2}
                maxLength={2000}
                placeholder="Reason (optional)"
                aria-label="Reason"
                className="w-full rounded-md border border-rose-200 bg-white p-2 text-sm text-slate-800"
              />
              <div className="flex gap-2">
                <Button
                  type="button"
                  size="sm"
                  onClick={() => run("reject")}
                  disabled={busy !== null}
                  className="bg-rose-600 text-white hover:bg-rose-700"
                >
                  {busy === "reject" ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
                  ) : null}
                  Reject
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={busy !== null}
                  onClick={() => setConfirmReject(false)}
                >
                  Keep them
                </Button>
              </div>
            </div>
          ) : null}
          {outcome ? (
            <div className="w-full text-sm" role="status">
              <p className="font-medium text-slate-800">{outcome.summary}</p>
              {outcome.failures.length ? (
                <ul className="mt-1 list-disc pl-5 text-rose-700">
                  {outcome.failures.map((failure) => (
                    <li key={`${failure.name}-${failure.detail}`}>
                      {failure.name}: {failure.detail}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}
          {error ? <p className="w-full text-sm font-medium text-rose-700">{error}</p> : null}
        </div>
      ) : null}

      <Card className="overflow-hidden py-0">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              {bulk ? (
                <TableHead className="w-10">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    disabled={selectable.length === 0}
                    onChange={() => setSelected(allSelected ? new Set() : new Set(selectable))}
                    aria-label="Select everyone who can be moved"
                  />
                </TableHead>
              ) : null}
              <TableHead>Name</TableHead>
              <TableHead className="hidden md:table-cell">Current role</TableHead>
              <TableHead className="hidden lg:table-cell">Location</TableHead>
              <TableHead className="hidden xl:table-cell">Skills</TableHead>
              <TableHead className="text-right">Stage</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {candidates.map((candidate) => {
              const application = bulk?.applications[candidate.id];
              return (
                <TableRow key={candidate.id}>
                  {bulk ? (
                    <TableCell>
                      <input
                        type="checkbox"
                        checked={application ? selected.has(application.applicationId) : false}
                        disabled={!application}
                        onChange={() => application && toggle(application.applicationId)}
                        aria-label={`Select ${fullName(candidate)}`}
                      />
                    </TableCell>
                  ) : null}
                  <TableCell>
                    <Link
                      href={`/candidates/${candidate.id}`}
                      className="flex items-center gap-3 font-medium hover:underline"
                    >
                      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-indigo-50 text-xs font-semibold text-indigo-700">
                        {initials(candidate)}
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate">{fullName(candidate)}</span>
                        <span className="block truncate text-xs font-normal text-slate-500">
                          {candidate.email ?? "No email"}
                        </span>
                      </span>
                    </Link>
                  </TableCell>
                  <TableCell className="hidden max-w-56 truncate text-slate-600 md:table-cell">
                    {candidate.current_position ?? candidate.position_applied ?? "Not listed"}
                    {candidate.current_company ? (
                      <span className="block text-xs text-slate-400">{candidate.current_company}</span>
                    ) : null}
                  </TableCell>
                  <TableCell className="hidden text-slate-600 lg:table-cell">
                    {candidate.location ?? "Not listed"}
                  </TableCell>
                  <TableCell className="hidden xl:table-cell">
                    <SkillChips skills={candidate.skills} />
                  </TableCell>
                  <TableCell className="text-right">
                    {bulk ? (
                      <span className="text-xs text-slate-600">
                        {application ? application.stageName : "Not in progress here"}
                      </span>
                    ) : (
                      <StageBadge status={candidate.status} />
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}

function SkillChips({ skills }: { skills: string[] | null | undefined }) {
  if (!skills?.length) return <span className="text-xs text-slate-400">None listed</span>;
  return (
    <span className="flex flex-wrap gap-1">
      {skills.slice(0, 3).map((skill) => (
        <span key={skill} className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">
          {skill}
        </span>
      ))}
      {skills.length > 3 ? (
        <span className="px-1 py-0.5 text-xs text-slate-400">+{skills.length - 3}</span>
      ) : null}
    </span>
  );
}
