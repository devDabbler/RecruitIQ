"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { CheckCircle2, CircleDashed, Loader2, Upload, XCircle } from "lucide-react";

import { FitChip } from "@/components/fit-chip";
import { SourceSelect } from "@/components/source-select";
import { ACCEPT, type SelectableJob } from "@/components/resume-uploader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ApplicantFit } from "@/lib/fit";
import {
  type UploadItem,
  candidateNameFromParse,
  describeError,
  queueFiles,
  rankedUploads,
  updateItem,
  uploadProgress,
} from "@/lib/intake";
import { DEFAULT_SOURCE } from "@/lib/sources";

const STATUS_LABELS: Record<UploadItem["status"], string> = {
  queued: "Waiting",
  parsing: "Reading the resume",
  saving: "Saving",
  done: "Added",
  failed: "Not added",
};

/**
 * Several resumes into one job's pipeline, one file at a time.
 *
 * Sequential on purpose: each parse is a model call of ten to thirty seconds,
 * and nginx rate-limits /api/resume/. Parallel uploads would trip the limit
 * and make the progress list lie about what is happening.
 */
export function BulkUploader({ jobs }: { jobs: SelectableJob[] }) {
  const [jobId, setJobId] = useState("");
  const [source, setSource] = useState<string>(DEFAULT_SOURCE);
  const [items, setItems] = useState<UploadItem[]>([]);
  const [skipped, setSkipped] = useState<string[]>([]);
  const [running, setRunning] = useState(false);
  const files = useRef<File[]>([]);
  const stop = useRef(false);
  const input = useRef<HTMLInputElement>(null);
  const progress = uploadProgress(items);
  // Once a batch is over, the new applicants are listed best fit first.
  const finished =
    !running &&
    items.length > 0 &&
    items.every((i) => i.status === "done" || i.status === "failed");
  const shown = finished ? rankedUploads(items) : items;
  const anyFit = items.some((i) => i.fit && !i.fit.hidden && typeof i.fit.score === "number");
  const job = jobs.find((j) => String(j.id) === jobId) ?? null;

  function choose(list: FileList | null) {
    if (!list || running) return;
    files.current = Array.from(list);
    const queued = queueFiles(files.current.map((f) => ({ name: f.name, size: f.size })));
    setItems(queued.items);
    setSkipped(queued.skipped);
  }

  async function processOne(item: UploadItem) {
    const file = files.current[item.index];
    const patch = (next: Partial<UploadItem>) =>
      setItems((current) => updateItem(current, item.id, next));
    patch({ status: "parsing", detail: undefined });
    try {
      const parseForm = new FormData();
      parseForm.set("file", file);
      const parsed = await fetch("/api/resume/parse", { method: "POST", body: parseForm });
      const parsedBody = (await parsed.json().catch(() => null)) as {
        success?: boolean;
        message?: string;
        detail?: unknown;
        personal_info?: Record<string, unknown> | null;
        parsed_data?: Record<string, unknown> | null;
      } | null;
      if (!parsed.ok || !parsedBody || parsedBody.success === false) {
        throw new Error(parsedBody?.message ?? describeError(parsedBody?.detail, parsed.status));
      }
      patch({ status: "saving", candidateName: candidateNameFromParse(parsedBody) ?? undefined });

      const saveForm = new FormData();
      saveForm.set("file", file);
      saveForm.set("parsed_data", JSON.stringify(parsedBody.parsed_data ?? {}));
      saveForm.set("job_id", jobId);
      saveForm.set("source", source);
      if (job) saveForm.set("position_applied", job.title);
      const saved = await fetch("/api/resume/save", { method: "POST", body: saveForm });
      const savedBody = (await saved.json().catch(() => null)) as {
        candidate_id?: string | null;
        already_in_pipeline?: boolean;
        fit?: ApplicantFit | null;
        detail?: unknown;
      } | null;
      if (!saved.ok || !savedBody?.candidate_id) {
        throw new Error(describeError(savedBody?.detail, saved.status));
      }
      patch({
        status: "done",
        candidateId: savedBody.candidate_id,
        fit: savedBody.fit ?? null,
        detail: savedBody.already_in_pipeline
          ? "Already in this pipeline. Resume updated."
          : undefined,
      });
    } catch (err) {
      patch({ status: "failed", detail: (err as Error).message });
    }
  }

  async function start() {
    if (!jobId || running) return;
    setRunning(true);
    stop.current = false;
    for (const item of items) {
      if (stop.current) break;
      if (item.status === "queued" || item.status === "failed") await processOne(item);
    }
    setRunning(false);
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardContent className="space-y-4 p-6">
          <button
            type="button"
            onClick={() => input.current?.click()}
            disabled={running}
            className="grid w-full cursor-pointer place-items-center gap-2 rounded-lg border-2 border-dashed border-slate-300 p-10 text-center hover:border-indigo-400"
          >
            <Upload className="h-6 w-6 text-slate-400" aria-hidden />
            <span className="font-medium text-slate-700">
              {items.length ? `${items.length} files ready` : "Choose up to 20 resumes"}
            </span>
            <span className="text-xs text-slate-500">
              PDF, Word, text, or an image. Up to 8 MB each.
            </span>
          </button>
          <input
            ref={input}
            type="file"
            accept={ACCEPT}
            multiple
            className="hidden"
            aria-label="Resume files"
            onChange={(e) => choose(e.target.files)}
          />

          <label className="block text-sm font-medium text-slate-700">
            Add everyone to
            <select
              value={jobId}
              onChange={(e) => setJobId(e.target.value)}
              disabled={running}
              className="mt-1 block w-full rounded-md border border-slate-200 bg-white px-2 py-2 text-sm font-normal text-slate-700"
            >
              <option value="">Choose a job</option>
              {jobs.map((j) => (
                <option key={j.id} value={j.id}>
                  {j.title} ({j.department})
                </option>
              ))}
            </select>
          </label>

          <label className="block text-sm font-medium text-slate-700">
            How did they find us?
            <SourceSelect
              id="bulk-source"
              value={source}
              onChange={setSource}
              disabled={running}
              className="mt-1 block w-full font-normal"
            />
            <span className="mt-1 block text-xs font-normal text-slate-500">
              One source for the whole batch. Upload separate batches for different sources.
            </span>
          </label>

          <div className="flex gap-2">
            <Button
              onClick={start}
              disabled={!jobId || items.length === 0 || running}
              className="flex-1"
            >
              {running ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden /> : null}
              {running
                ? "Adding"
                : progress.failed
                  ? "Retry the ones not added"
                  : "Add to pipeline"}
            </Button>
            {running ? (
              <Button variant="outline" onClick={() => (stop.current = true)}>
                Stop after this file
              </Button>
            ) : null}
          </div>

          {skipped.length ? (
            <ul className="space-y-1 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
              {skipped.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Progress</CardTitle>
        </CardHeader>
        <CardContent>
          {items.length === 0 ? (
            <p className="text-sm text-slate-500">
              Each file is read and saved in turn. Results appear here.
            </p>
          ) : (
            <>
              <p className="mb-3 text-xs text-slate-500" role="status">
                {progress.done} of {progress.total} added
                {progress.failed ? `, ${progress.failed} not added` : ""}
                {finished && anyFit ? ". Best fit for the job first." : ""}
              </p>
              <ul className="space-y-2 text-sm">
                {shown.map((item) => (
                  <li key={item.id} className="flex items-start gap-2">
                    <StatusIcon status={item.status} />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-slate-800">
                        {item.candidateId ? (
                          <Link
                            href={`/candidates/${item.candidateId}`}
                            className="hover:underline"
                          >
                            {item.candidateName ?? item.fileName}
                          </Link>
                        ) : (
                          (item.candidateName ?? item.fileName)
                        )}
                      </span>
                      <span className="block text-xs text-slate-500">
                        {STATUS_LABELS[item.status]}
                        {item.detail ? `. ${item.detail}` : ""}
                      </span>
                    </span>
                    {item.status === "done" && item.fit ? <FitChip fit={item.fit} /> : null}
                  </li>
                ))}
              </ul>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function StatusIcon({ status }: { status: UploadItem["status"] }) {
  if (status === "done") {
    return <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-600" aria-hidden />;
  }
  if (status === "failed") return <XCircle className="mt-0.5 h-4 w-4 text-rose-600" aria-hidden />;
  if (status === "queued") {
    return <CircleDashed className="mt-0.5 h-4 w-4 text-slate-300" aria-hidden />;
  }
  return <Loader2 className="mt-0.5 h-4 w-4 animate-spin text-indigo-600" aria-hidden />;
}
