"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowDown, ArrowRight, ArrowUp, Loader2, Tag, X } from "lucide-react";

import { FitChip } from "@/components/fit-chip";
import { StageBadge } from "@/components/stage-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  type BulkTagResult,
  type BulkTransitionResult,
  type Candidate,
  fullName,
  initials,
} from "@/lib/domain";
import type { FitSort } from "@/lib/fit";
import {
  type ActiveApplication,
  TAG_GUIDANCE,
  bulkSummary,
  bulkTagSummary,
  describeError,
  normalizeTag,
  selectionLabel,
} from "@/lib/intake";

/** Present when the list is filtered to one job: who can be moved, and where they are. */
export interface BulkContext {
  jobTitle: string;
  applications: Record<string, ActiveApplication>;
}

/** Present when the list is filtered to one job: the Fit column and its sort links. */
export interface FitColumn {
  sort: FitSort;
  /** Link that flips the order (best first <-> worst first). */
  toggleHref: string;
}

interface Outcome {
  summary: string;
  failures: { name: string; detail: string }[];
}

/**
 * The candidates table. A writer gets checkboxes and a bar to tag the
 * selection (Track 2 Phase 5); with a job filter the bar can also advance or
 * reject it. Every candidate the server could not tag or move is listed by
 * name with the reason, because the server handles the rest anyway.
 */
export function CandidateTable({
  candidates,
  bulk,
  fit = null,
  taggable = false,
}: {
  candidates: Candidate[];
  bulk: BulkContext | null;
  fit?: FitColumn | null;
  /** Show checkboxes and the Tag action. Writers only; the API refuses the rest. */
  taggable?: boolean;
}) {
  const router = useRouter();
  // Candidate ids. Advance and Reject send the matching application ids.
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [confirmReject, setConfirmReject] = useState(false);
  const [tagging, setTagging] = useState(false);
  const [tagDraft, setTagDraft] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<"advance" | "reject" | "tag" | null>(null);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selecting = taggable || bulk !== null;
  const selectable = useMemo(
    () =>
      taggable
        ? candidates.map((c) => c.id)
        : bulk
          ? candidates.filter((c) => bulk.applications[c.id]).map((c) => c.id)
          : [],
    [bulk, candidates, taggable],
  );
  const allSelected = selectable.length > 0 && selectable.every((id) => selected.has(id));
  const movable = bulk
    ? [...selected].flatMap((id) =>
        bulk.applications[id] ? [bulk.applications[id].applicationId] : [],
      )
    : [];
  const tagPreview = tagDraft.trim() ? normalizeTag(tagDraft) : "";

  function toggle(id: string) {
    setSelected((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function runTag() {
    if (busy || selected.size === 0 || !tagPreview) return;
    setBusy("tag");
    setError(null);
    setOutcome(null);
    try {
      const response = await fetch("/api/candidates/bulk/tag", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ candidate_ids: [...selected], tag: tagDraft }),
      });
      const payload = (await response.json().catch(() => null)) as
        (BulkTagResult & { detail?: unknown }) | null;
      if (!response.ok || !payload?.results) {
        throw new Error(describeError(payload?.detail, response.status));
      }
      setOutcome({
        summary: bulkTagSummary(payload.tag, payload.succeeded, payload.failed),
        failures: payload.results
          .filter((r) => !r.ok)
          .map((r) => ({
            name: r.candidate_name ?? "A candidate",
            detail: r.detail ?? "Not tagged.",
          })),
      });
      setSelected(new Set());
      setTagging(false);
      setTagDraft("");
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function run(action: "advance" | "reject") {
    if (busy || movable.length === 0) return;
    setBusy(action);
    setError(null);
    setOutcome(null);
    try {
      const response = await fetch(`/api/applications/bulk/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          application_ids: movable,
          note: action === "reject" ? note.trim() || null : null,
        }),
      });
      const payload = (await response.json().catch(() => null)) as
        (BulkTransitionResult & { detail?: unknown }) | null;
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
      {selecting ? (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-white p-3 text-sm">
          <span className="text-slate-600">
            {selectionLabel(selected.size, movable.length, bulk?.jobTitle ?? null)}
          </span>
          <span className="ml-auto flex flex-wrap gap-2">
            {taggable ? (
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => {
                  setTagging(true);
                  setConfirmReject(false);
                }}
                disabled={selected.size === 0 || busy !== null}
              >
                <Tag className="mr-2 h-4 w-4" aria-hidden />
                Tag
              </Button>
            ) : null}
            {bulk ? (
              <>
                <Button
                  type="button"
                  size="sm"
                  onClick={() => run("advance")}
                  disabled={movable.length === 0 || busy !== null}
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
                  onClick={() => {
                    setConfirmReject(true);
                    setTagging(false);
                  }}
                  disabled={movable.length === 0 || busy !== null}
                >
                  <X className="mr-2 h-4 w-4" aria-hidden />
                  Reject
                </Button>
              </>
            ) : null}
          </span>
          {tagging ? (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                runTag();
              }}
              className="w-full space-y-1 rounded-md border border-indigo-200 bg-indigo-50 p-3"
            >
              <div className="flex flex-wrap gap-2">
                <Input
                  value={tagDraft}
                  onChange={(e) => setTagDraft(e.target.value)}
                  placeholder="Tag to add"
                  aria-label="Tag to add to the selected candidates"
                  maxLength={80}
                  autoFocus
                  className="h-8 max-w-xs bg-white text-sm"
                />
                <Button type="submit" size="sm" disabled={!tagPreview || busy !== null}>
                  {busy === "tag" ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
                  ) : null}
                  Tag {selected.size} {selected.size === 1 ? "candidate" : "candidates"}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={busy !== null}
                  onClick={() => setTagging(false)}
                >
                  Cancel
                </Button>
              </div>
              {tagDraft.trim() && tagPreview !== tagDraft.trim() ? (
                <p className="text-xs text-slate-600">
                  {tagPreview ? `Saved as ${tagPreview}` : "Use at least one letter or number."}
                </p>
              ) : null}
              <p className="text-xs text-slate-500">{TAG_GUIDANCE}</p>
            </form>
          ) : null}
          {bulk && confirmReject ? (
            <div
              role="alertdialog"
              aria-label="Reject the selected candidates?"
              className="w-full space-y-2 rounded-md border border-rose-200 bg-rose-50 p-3"
            >
              <p className="font-medium text-rose-900">
                Reject {movable.length} {movable.length === 1 ? "candidate" : "candidates"} in{" "}
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
              {selecting ? (
                <TableHead className="w-10">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    disabled={selectable.length === 0}
                    onChange={() => setSelected(allSelected ? new Set() : new Set(selectable))}
                    aria-label={
                      taggable ? "Select everyone on this page" : "Select everyone who can be moved"
                    }
                  />
                </TableHead>
              ) : null}
              <TableHead>Name</TableHead>
              {fit ? (
                <TableHead className="w-24">
                  <Link
                    href={fit.toggleHref}
                    className="inline-flex items-center gap-1 hover:text-slate-900"
                    aria-label={
                      fit.sort === "best"
                        ? "Fit, best first. Show worst first."
                        : "Fit, worst first. Show best first."
                    }
                  >
                    Fit
                    {fit.sort === "best" ? (
                      <ArrowDown className="h-3.5 w-3.5" aria-hidden />
                    ) : (
                      <ArrowUp className="h-3.5 w-3.5" aria-hidden />
                    )}
                  </Link>
                </TableHead>
              ) : null}
              <TableHead className="hidden md:table-cell">Current role</TableHead>
              <TableHead className="hidden lg:table-cell">Location</TableHead>
              <TableHead className="hidden xl:table-cell">Skills</TableHead>
              <TableHead className="hidden lg:table-cell">Tags</TableHead>
              <TableHead className="text-right">Stage</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {candidates.map((candidate) => {
              const application = bulk?.applications[candidate.id];
              return (
                <TableRow key={candidate.id}>
                  {selecting ? (
                    <TableCell>
                      <input
                        type="checkbox"
                        checked={selected.has(candidate.id)}
                        disabled={!taggable && !application}
                        onChange={() => toggle(candidate.id)}
                        aria-label={`Select ${fullName(candidate)}`}
                      />
                    </TableCell>
                  ) : null}
                  <TableCell className="max-w-52 sm:max-w-none">
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
                  {fit ? (
                    <TableCell>
                      <FitChip fit={candidate.fit} />
                    </TableCell>
                  ) : null}
                  <TableCell className="hidden max-w-56 truncate text-slate-600 md:table-cell">
                    {candidate.current_position ?? candidate.position_applied ?? "Not listed"}
                    {candidate.current_company ? (
                      <span className="block text-xs text-slate-400">
                        {candidate.current_company}
                      </span>
                    ) : null}
                  </TableCell>
                  <TableCell className="hidden text-slate-600 lg:table-cell">
                    {candidate.location ?? "Not listed"}
                  </TableCell>
                  <TableCell className="hidden xl:table-cell">
                    <SkillChips skills={candidate.skills} />
                  </TableCell>
                  <TableCell className="hidden lg:table-cell">
                    <TagChips tags={candidate.tags} />
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

function TagChips({ tags }: { tags: string[] | undefined }) {
  if (!tags?.length) return <span className="text-xs text-slate-400">None</span>;
  return (
    <span className="flex flex-wrap gap-1">
      {tags.slice(0, 3).map((tag) => (
        <span
          key={tag}
          className="rounded-full border border-indigo-200 bg-indigo-50 px-1.5 py-0.5 text-xs text-indigo-700"
        >
          {tag}
        </span>
      ))}
      {tags.length > 3 ? (
        <span className="px-1 py-0.5 text-xs text-slate-400" title={tags.slice(3).join(", ")}>
          +{tags.length - 3}
        </span>
      ) : null}
    </span>
  );
}
