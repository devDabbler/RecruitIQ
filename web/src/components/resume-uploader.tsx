"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { FileText, Loader2, Target, Upload, UserPlus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { humanize } from "@/lib/format";
import { cn } from "@/lib/utils";

const ACCEPT = ".pdf,.docx,.doc,.txt,.jpg,.jpeg,.png";

/** The sentinel for "score against a role that is not in the database". */
export const OTHER_ROLE = "__other__";
/** The sentinel for "do not score fit at all". */
export const NO_ROLE = "__none__";

export interface SelectableJob {
  id: number;
  title: string;
  department: string;
  status: string;
}

interface ParsedResume {
  success?: boolean;
  message?: string;
  personal_info?: Record<string, unknown> | null;
  skills?: unknown;
  experience?: Record<string, unknown>[] | null;
  education?: Record<string, unknown>[] | null;
  parsed_data?: Record<string, unknown> | null;
  job_fit_score?: number | null;
  hiring_recommendation?: {
    recommendation?: string;
    details?: string;
    decision?: string;
  } | null;
  market_alignment?: {
    target_job_title?: string;
    // "job" when the score came from a real requisition's own skills, "market"
    // when it was estimated from similar roles. Absent on older responses.
    source?: "job" | "market";
    matching_skills?: string[];
    missing_skills?: string[];
    commentary?: string;
  } | null;
  quality_assessment?: {
    clarity_score?: number;
    impact_score?: number;
    skills_relevance_score?: number;
    overall_feedback?: string;
  } | null;
  skill_suggestions?: {
    technical_skills?: string[];
    soft_skills?: string[];
    certifications?: string[];
    recommendations?: string;
  } | null;
}

/**
 * Drop a resume in, see what the parser extracted.
 *
 * Parsing itself writes nothing: the parse route pins `save_to_db=false`, so
 * the public demo cannot fill the database with strangers' resumes. When the
 * session can write (admin), a reviewed parse can then be saved as a candidate
 * through /api/resume/save.
 */
export function ResumeUploader({
  canWrite = false,
  jobs = [],
}: {
  canWrite?: boolean;
  jobs?: SelectableJob[];
}) {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  // Either a job id as a string, OTHER_ROLE, or NO_ROLE.
  const [roleChoice, setRoleChoice] = useState<string>(NO_ROLE);
  const [customRole, setCustomRole] = useState("");
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState<ParsedResume | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const selectedJob = jobs.find((job) => String(job.id) === roleChoice) ?? null;
  /** What to store as the position when saving a candidate. */
  const roleLabel = selectedJob?.title ?? (roleChoice === OTHER_ROLE ? customRole.trim() : "");

  async function submit(fileOverride?: File, choiceOverride?: string, customOverride?: string) {
    const chosen = fileOverride ?? file;
    const choice = choiceOverride ?? roleChoice;
    const custom = customOverride ?? customRole;
    if (!chosen || busy) return;
    setBusy(true);
    setError(null);
    setResult(null);

    try {
      const form = new FormData();
      form.set("file", chosen);

      // A real requisition is sent as job_id so the backend scores against that
      // job's own required skills. Free text can only be compared to similar
      // roles, which is a weaker claim, and the fit card says so.
      const job = jobs.find((j) => String(j.id) === choice);
      if (job) {
        form.set("job_id", String(job.id));
      } else if (choice === OTHER_ROLE && custom.trim()) {
        form.set("target_job_title", custom.trim());
      }

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

  /**
   * One click, no file needed: fetch the bundled synthetic resume and parse it
   * against a seeded role. Most visitors should never have to upload anything
   * real to see the feature work.
   */
  async function trySample() {
    if (busy) return;
    setError(null);
    try {
      const response = await fetch("/sample-resume.docx");
      if (!response.ok) throw new Error("Could not load the sample resume.");
      const blob = await response.blob();
      const sample = new File([blob], "sample-resume.docx", {
        type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      });

      // Prefer a real seeded requisition so the sample demonstrates the
      // job-backed score rather than the market estimate. Falls back to the
      // free-text title on a database that has not been seeded.
      const preferred =
        jobs.find((job) => /machine learning/i.test(job.title)) ??
        jobs.find((job) => job.status === "open") ??
        null;
      const choice = preferred ? String(preferred.id) : OTHER_ROLE;
      const custom = preferred ? "" : "Machine Learning Engineer";

      setFile(sample);
      setRoleChoice(choice);
      setCustomRole(custom);
      await submit(sample, choice, custom);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function save() {
    if (!file || !result || saving) return;
    setSaving(true);
    setError(null);
    try {
      const form = new FormData();
      form.set("file", file);
      form.set("parsed_data", JSON.stringify(result.parsed_data ?? {}));
      if (roleLabel) form.set("position_applied", roleLabel);

      const response = await fetch("/api/resume/save", { method: "POST", body: form });
      const payload = (await response.json().catch(() => null)) as {
        success?: boolean;
        candidate_id?: string | null;
        detail?: string;
        message?: string;
      } | null;

      if (!response.ok || payload?.success === false || !payload?.candidate_id) {
        throw new Error(
          payload?.detail || payload?.message || `Saving failed (${response.status})`,
        );
      }
      router.push(`/candidates/${payload.candidate_id}`);
    } catch (e) {
      setError((e as Error).message);
      setSaving(false);
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

          <div className="space-y-2">
            <label htmlFor="score-against" className="block text-sm font-medium text-slate-700">
              Score against <span className="font-normal text-slate-400">(optional)</span>
            </label>
            {/* Base UI types the change value as nullable; clearing the
                selection is the same as choosing not to score fit. */}
            <Select value={roleChoice} onValueChange={(next) => setRoleChoice(next ?? NO_ROLE)}>
              <SelectTrigger id="score-against" className="h-10 w-full bg-white">
                <SelectValue>
                  {selectedJob ? (
                    <span className="truncate">
                      {selectedJob.title}
                      <span className="text-slate-400"> · {selectedJob.department}</span>
                    </span>
                  ) : roleChoice === OTHER_ROLE ? (
                    "Another role"
                  ) : (
                    "No fit scoring"
                  )}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NO_ROLE}>No fit scoring</SelectItem>
                {jobs.map((job) => (
                  <SelectItem key={job.id} value={String(job.id)}>
                    <span className="flex min-w-0 flex-col items-start text-left">
                      <span className="truncate font-medium">{job.title}</span>
                      <span className="truncate text-xs text-slate-500">
                        {job.department}
                        {job.status === "open" ? "" : ` · ${humanize(job.status)}`}
                      </span>
                    </span>
                  </SelectItem>
                ))}
                <SelectItem value={OTHER_ROLE}>Another role...</SelectItem>
              </SelectContent>
            </Select>

            {roleChoice === OTHER_ROLE ? (
              <input
                value={customRole}
                onChange={(e) => setCustomRole(e.target.value)}
                placeholder="Senior Backend Engineer"
                aria-label="Other role"
                className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
              />
            ) : null}

            <p className="text-xs text-slate-500">
              {selectedJob
                ? "Fit is scored against the skills this role actually requires."
                : roleChoice === OTHER_ROLE
                  ? "This role is not in the database, so fit is estimated from similar roles rather than a real opening."
                  : jobs.length === 0
                    ? "No jobs are available to score against right now."
                    : "Pick a role to also score how well this resume fits it."}
            </p>
          </div>

          <Button onClick={() => submit()} disabled={!file || busy || saving} className="w-full">
            {busy ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Parsing…
              </>
            ) : (
              "Parse resume"
            )}
          </Button>

          <Button
            onClick={trySample}
            disabled={busy || saving}
            variant="outline"
            className="w-full"
          >
            <FileText className="mr-2 h-4 w-4" aria-hidden />
            Try a sample resume
          </Button>

          {canWrite && result && !busy ? (
            <Button
              onClick={save}
              disabled={saving}
              variant="outline"
              className="w-full border-emerald-300 text-emerald-700 hover:bg-emerald-50 hover:text-emerald-800"
            >
              {saving ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving…
                </>
              ) : (
                <>
                  <UserPlus className="mr-2 h-4 w-4" aria-hidden />
                  Save as candidate
                </>
              )}
            </Button>
          ) : null}

          <p className="text-xs text-slate-500">
            {canWrite
              ? "Parsing alone saves nothing. Save as candidate adds this person to the pipeline with the resume attached."
              : "Files are parsed in memory and discarded, never stored. Extraction uses a third-party AI service, so please use the sample rather than a real person's resume."}
          </p>

          {error ? (
            <p className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
              {error}
            </p>
          ) : null}
        </CardContent>
      </Card>

      <div className="space-y-6">
        {result && !busy ? <FitCard result={result} /> : null}

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
    </div>
  );
}

const DECISION_CLASSES: Record<string, string> = {
  yes: "border-emerald-200 bg-emerald-50 text-emerald-700",
  maybe: "border-amber-200 bg-amber-50 text-amber-700",
  no: "border-rose-200 bg-rose-50 text-rose-700",
};

/** Target-role analysis: fit score, skill overlap, and resume quality. */
function FitCard({ result }: { result: ParsedResume }) {
  const score = result.job_fit_score;
  const alignment = result.market_alignment;
  const recommendation = result.hiring_recommendation;
  const quality = result.quality_assessment;

  // No target role given: the parse ran without fit analysis, show nothing.
  if (score == null && !alignment?.target_job_title) return null;

  const matched = (alignment?.matching_skills ?? []).slice(0, 12);
  const missing = (alignment?.missing_skills ?? []).slice(0, 12);
  const missingOverflow = (alignment?.missing_skills?.length ?? 0) - missing.length;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Target className="h-4 w-4" aria-hidden />
          Fit for {alignment?.target_job_title ?? "the target role"}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        {/* Say which baseline produced the number. A score against a real
            requisition and a score against "roles like this one" are different
            claims, and presenting them identically overstates the second. */}
        <p className="text-xs text-slate-500">
          {alignment?.source === "job"
            ? "Scored against the skills this requisition requires."
            : "Estimated from roles similar to this title. No matching requisition was used."}
        </p>

        <div className="flex flex-wrap items-center gap-3">
          {score != null ? (
            <span className="text-2xl font-semibold tabular-nums">
              {score.toFixed(1)}
              <span className="text-sm font-normal text-slate-400"> / 10</span>
            </span>
          ) : null}
          {recommendation?.recommendation ? (
            <span
              className={cn(
                "rounded-full border px-2.5 py-0.5 text-xs font-medium",
                DECISION_CLASSES[recommendation.decision ?? ""] ??
                  "border-slate-200 bg-slate-50 text-slate-600",
              )}
            >
              {recommendation.recommendation}
            </span>
          ) : null}
        </div>

        {recommendation?.details ? (
          <p className="text-slate-600">{recommendation.details}</p>
        ) : null}

        {matched.length ? (
          <div>
            <h3 className="mb-2 text-xs font-medium tracking-wide text-slate-400 uppercase">
              Skills the market asks for and this resume has
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {matched.map((skill) => (
                <span
                  key={skill}
                  className="rounded bg-emerald-50 px-2 py-0.5 text-xs text-emerald-700"
                >
                  {skill}
                </span>
              ))}
            </div>
          </div>
        ) : null}

        {missing.length ? (
          <div>
            <h3 className="mb-2 text-xs font-medium tracking-wide text-slate-400 uppercase">
              In demand for this role, not on the resume
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {missing.map((skill) => (
                <span
                  key={skill}
                  className="rounded bg-amber-50 px-2 py-0.5 text-xs text-amber-700"
                >
                  {skill}
                </span>
              ))}
              {missingOverflow > 0 ? (
                <span className="px-1 py-0.5 text-xs text-slate-400">
                  +{missingOverflow} more
                </span>
              ) : null}
            </div>
          </div>
        ) : null}

        {quality ? (
          <div>
            <h3 className="mb-2 text-xs font-medium tracking-wide text-slate-400 uppercase">
              Resume quality
            </h3>
            <div className="flex flex-wrap gap-x-6 gap-y-1">
              <QualityMeter label="Clarity" value={quality.clarity_score} />
              <QualityMeter label="Impact" value={quality.impact_score} />
              <QualityMeter label="Relevance" value={quality.skills_relevance_score} />
            </div>
            {quality.overall_feedback ? (
              <p className="mt-2 text-xs text-slate-500">{quality.overall_feedback}</p>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function QualityMeter({ label, value }: { label: string; value: number | undefined }) {
  if (value == null) return null;
  const pct = Math.min(100, Math.max(0, value * 10));
  return (
    <span className="flex items-center gap-2 text-xs text-slate-500">
      <span className="w-16 shrink-0">{label}</span>
      <span className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-100">
        <span
          className={cn(
            "block h-full rounded-full",
            pct >= 70 ? "bg-emerald-500" : pct >= 40 ? "bg-blue-500" : "bg-amber-500",
          )}
          style={{ width: `${pct}%` }}
        />
      </span>
      <span className="tabular-nums">{value}</span>
    </span>
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
