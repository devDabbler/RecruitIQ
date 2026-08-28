"use client";

import { useRef, useState } from "react";
import { FileText, Loader2, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const ACCEPT = ".pdf,.docx,.doc,.txt,.jpg,.jpeg,.png";

interface ParsedResume {
  success?: boolean;
  message?: string;
  personal_info?: Record<string, unknown> | null;
  skills?: unknown;
  experience?: Record<string, unknown>[] | null;
  education?: Record<string, unknown>[] | null;
  parsed_data?: Record<string, unknown> | null;
}

/**
 * Drop a resume in, see what the parser extracted.
 *
 * Nothing is written: the route handler pins `save_to_db=false`, so this
 * demonstrates the extraction without the demo turning into a pile of
 * strangers' resumes. The screen says so rather than leaving it a surprise.
 */
export function ResumeUploader() {
  const [file, setFile] = useState<File | null>(null);
  const [targetJob, setTargetJob] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ParsedResume | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  async function submit() {
    if (!file || busy) return;
    setBusy(true);
    setError(null);
    setResult(null);

    try {
      const form = new FormData();
      form.set("file", file);
      if (targetJob.trim()) form.set("target_job_title", targetJob.trim());

      const response = await fetch("/api/resume/parse", { method: "POST", body: form });
      const payload = (await response.json().catch(() => null)) as
        | (ParsedResume & { detail?: string })
        | null;

      if (!response.ok || payload?.success === false) {
        throw new Error(
          payload?.detail || payload?.message || `Parsing failed (${response.status})`,
        );
      }
      setResult(payload);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardContent className="space-y-4 p-6">
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              const dropped = e.dataTransfer.files?.[0];
              if (dropped) setFile(dropped);
            }}
            onClick={() => input.current?.click()}
            className={cn(
              "grid cursor-pointer place-items-center gap-2 rounded-lg border-2 border-dashed p-10 text-center transition-colors",
              dragging
                ? "border-indigo-500 bg-indigo-50/50"
                : "border-slate-300 hover:border-indigo-400",
            )}
          >
            <Upload className="h-6 w-6 text-slate-400" aria-hidden />
            {file ? (
              <>
                <p className="font-medium text-slate-800">{file.name}</p>
                <p className="text-xs text-slate-500">
                  {(file.size / 1024).toFixed(0)} KB. Click to choose a different file.
                </p>
              </>
            ) : (
              <>
                <p className="font-medium text-slate-700">Drop a resume here</p>
                <p className="text-xs text-slate-500">PDF, Word, text, or an image. Up to 8 MB.</p>
              </>
            )}
            <input
              ref={input}
              type="file"
              accept={ACCEPT}
              className="hidden"
              aria-label="Resume file"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>

          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">
              Target role <span className="font-normal text-slate-400">(optional)</span>
            </span>
            <input
              value={targetJob}
              onChange={(e) => setTargetJob(e.target.value)}
              placeholder="Senior Backend Engineer"
              className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
            />
            <span className="mt-1 block text-xs text-slate-500">
              Given a role, the parser also scores fit against it.
            </span>
          </label>

          <Button onClick={submit} disabled={!file || busy} className="w-full">
            {busy ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Parsing…
              </>
            ) : (
              "Parse resume"
            )}
          </Button>

          <p className="text-xs text-slate-500">
            Nothing is saved. This demo parses the file and discards it.
          </p>

          {error ? (
            <p className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
              {error}
            </p>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <FileText className="h-4 w-4" aria-hidden />
            Extracted
          </CardTitle>
        </CardHeader>
        <CardContent>
          {busy ? (
            <p className="text-sm text-slate-500">
              Extracting text, then structuring it with the model. Ten to thirty seconds.
            </p>
          ) : result ? (
            <ParsedView result={result} />
          ) : (
            <p className="text-sm text-slate-500">
              Parsed contact details, skills, experience, and education appear here.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function ParsedView({ result }: { result: ParsedResume }) {
  const personal = result.personal_info ?? {};
  // The parser returns skills as strings on some paths and objects on others;
  // normalise rather than rendering "[object Object]".
  const skills = Array.isArray(result.skills)
    ? result.skills.map((skill) =>
        typeof skill === "string" ? skill : String((skill as Record<string, unknown>)?.name ?? ""),
      )
    : [];

  return (
    <div className="space-y-5 text-sm">
      {Object.keys(personal).length ? (
        <section>
          <h3 className="mb-2 text-xs font-medium tracking-wide text-slate-400 uppercase">
            Contact
          </h3>
          <dl className="space-y-1">
            {Object.entries(personal)
              .filter(([, value]) => value)
              .map(([key, value]) => (
                <div key={key} className="flex justify-between gap-3">
                  <dt className="text-slate-500 capitalize">{key.replace(/_/g, " ")}</dt>
                  <dd className="truncate text-right text-slate-800">{String(value)}</dd>
                </div>
              ))}
          </dl>
        </section>
      ) : null}

      {skills.filter(Boolean).length ? (
        <section>
          <h3 className="mb-2 text-xs font-medium tracking-wide text-slate-400 uppercase">
            Skills
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {skills.filter(Boolean).map((skill) => (
              <span key={skill} className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-700">
                {skill}
              </span>
            ))}
          </div>
        </section>
      ) : null}

      <Entries title="Experience" rows={result.experience} primary="title" secondary="company" />
      <Entries title="Education" rows={result.education} primary="degree" secondary="institution" />

      {!Object.keys(personal).length && !skills.length && !result.experience?.length ? (
        <p className="text-slate-500">
          {result.message ?? "The parser returned no structured fields for this file."}
        </p>
      ) : null}
    </div>
  );
}

function Entries({
  title,
  rows,
  primary,
  secondary,
}: {
  title: string;
  rows: Record<string, unknown>[] | null | undefined;
  primary: string;
  secondary: string;
}) {
  if (!rows?.length) return null;
  return (
    <section>
      <h3 className="mb-2 text-xs font-medium tracking-wide text-slate-400 uppercase">{title}</h3>
      <ul className="space-y-2">
        {rows.map((row, i) => (
          <li key={i} className="rounded border border-slate-200 p-3">
            <p className="font-medium text-slate-800">
              {String(row[primary] ?? row.name ?? "Untitled")}
            </p>
            <p className="text-xs text-slate-500">
              {[row[secondary], row.dates ?? row.duration ?? row.year]
                .filter(Boolean)
                .map(String)
                .join(" · ")}
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}
