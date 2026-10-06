"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronDown, Loader2, Save, Sparkles, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  EDUCATION_LEVELS,
  EMPTY_JOB,
  EXPERIENCE_LEVELS,
  JOB_STATUSES,
  JOB_TYPES,
  LOCATION_TYPES,
  addSkills,
  applyDraft,
  canRequestDraft,
  departmentChoices,
  draftRequestFrom,
  hasWrittenDescription,
  toJobPayload,
  validateJob,
  type DescriptionDraft,
  type FieldErrors,
  type JobFormValues,
} from "@/lib/job-form";
import { cn } from "@/lib/utils";

/**
 * Create or edit a job.
 *
 * Title and skills are given visual priority because they carry the matching:
 * the score is 45% title similarity and 35% skill overlap, so a vague title or
 * an empty skill list produces bad matches no matter how good the prose is.
 * The rest of the fields are display metadata and are laid out accordingly.
 */
export function JobForm({
  initial,
  jobId,
  canDraft = false,
  departments,
}: {
  initial?: JobFormValues;
  jobId?: number;
  /** Show "Draft with AI" (ATS Phase E). Only for job writers. */
  canDraft?: boolean;
  /** Track 2 Phase 3: active department names, from GET /api/departments. */
  departments: string[];
}) {
  const router = useRouter();
  const editing = jobId != null;
  const [values, setValues] = useState<JobFormValues>(initial ?? EMPTY_JOB);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showMore, setShowMore] = useState(false);
  const [drafting, setDrafting] = useState(false);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [pendingDraft, setPendingDraft] = useState<DescriptionDraft | null>(null);
  const [drafted, setDrafted] = useState(false);
  const departmentOptions = departmentChoices(departments, initial?.department ?? "").map(
    (name) => ({ value: name, label: name }),
  );

  /** Ask for an AI draft; never overwrite typed text without asking first. */
  async function requestDraft() {
    if (!canRequestDraft(values)) {
      setErrors((current) => ({ ...current, title: "Add a title first. The draft is written from it." }));
      return;
    }
    setDrafting(true);
    setDraftError(null);
    try {
      const response = await fetch("/api/job-drafts/description", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(draftRequestFrom(values)),
      });
      const payload = (await response.json().catch(() => null)) as
        | (DescriptionDraft & { detail?: unknown })
        | null;
      if (!response.ok || !payload) {
        throw new Error(readDetail(payload) || `Could not draft a description (${response.status})`);
      }
      const draft = {
        job_overview: payload.job_overview,
        required_qualifications: payload.required_qualifications,
      };
      if (hasWrittenDescription(values)) {
        setPendingDraft(draft);
      } else {
        setValues((current) => applyDraft(current, draft));
        setDrafted(true);
      }
    } catch (err) {
      setDraftError((err as Error).message);
    } finally {
      setDrafting(false);
    }
  }

  function set<K extends keyof JobFormValues>(key: K, value: JobFormValues[K]) {
    setValues((current) => ({ ...current, [key]: value }));
    // Clear the field's error as soon as it is touched; re-validated on submit.
    setErrors((current) => (current[key] ? { ...current, [key]: undefined } : current));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;

    const found = validateJob(values);
    if (Object.keys(found).length > 0) {
      setErrors(found);
      setFormError(null);
      return;
    }

    setBusy(true);
    setFormError(null);
    try {
      const response = await fetch(editing ? `/api/jobs/${jobId}` : "/api/jobs", {
        method: editing ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(toJobPayload(values)),
      });
      const payload = (await response.json().catch(() => null)) as
        | { id?: number; detail?: unknown }
        | null;

      if (!response.ok) {
        throw new Error(readDetail(payload) || `Could not save the job (${response.status})`);
      }

      const id = editing ? jobId : payload?.id;
      router.push(id ? `/jobs/${id}` : "/jobs");
      router.refresh();
    } catch (err) {
      setFormError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-6">
      <Card>
        <CardContent className="space-y-5 p-6">
          <div>
            <h2 className="text-sm font-semibold text-slate-800">What the role is</h2>
            <p className="mt-0.5 text-xs text-slate-500">
              Title and skills drive candidate matching. The more precisely they read, the
              better the ranking.
            </p>
          </div>

          <Field label="Title" error={errors.title} required>
            <Input
              value={values.title}
              onChange={(e) => set("title", e.target.value)}
              placeholder="Senior Machine Learning Engineer"
              aria-invalid={!!errors.title}
            />
          </Field>

          <Field
            label="Required skills"
            error={errors.skills}
            hint="Comma separated. These are matched against candidate skills directly."
          >
            <Input
              value={values.skills}
              onChange={(e) => set("skills", e.target.value)}
              placeholder="Python, PyTorch, MLOps, AWS"
            />
          </Field>

          <div className="grid gap-5 sm:grid-cols-2">
            <Field
              label="Department"
              error={errors.department}
              hint={
                departmentOptions.length === 0
                  ? "No departments yet. An admin adds them on the Team page."
                  : undefined
              }
              required
            >
              <Choice
                value={values.department}
                onChange={(v) => set("department", v)}
                options={departmentOptions}
                label="Department"
              />
            </Field>

            <Field
              label="Requisition number"
              error={errors.requisition_number}
              hint="From your HR system, so this job lines up with it. Must be unique."
            >
              <Input
                value={values.requisition_number}
                onChange={(e) => set("requisition_number", e.target.value)}
                placeholder="REQ-2026-0141"
                maxLength={40}
                aria-invalid={!!errors.requisition_number}
              />
            </Field>
          </div>

          {canDraft ? (
            <div className="space-y-2 rounded-md border border-indigo-100 bg-indigo-50/50 p-3 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs text-slate-600">
                  Draft the overview and qualifications from the title, department, level, and
                  skills above. Only those fields are sent. No candidate data is included.
                </p>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={requestDraft}
                  disabled={drafting}
                >
                  {drafting ? (
                    <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" aria-hidden />
                  ) : (
                    <Sparkles className="mr-1 h-3.5 w-3.5" aria-hidden />
                  )}
                  Draft with AI
                </Button>
              </div>
              {pendingDraft ? (
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs text-slate-700">
                    Replace the overview and qualifications you have written?
                  </span>
                  <Button
                    type="button"
                    size="sm"
                    onClick={() => {
                      setValues((current) => applyDraft(current, pendingDraft));
                      setPendingDraft(null);
                      setDrafted(true);
                    }}
                  >
                    Replace
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => setPendingDraft(null)}
                  >
                    Keep mine
                  </Button>
                </div>
              ) : null}
              {drafted ? (
                <p className="text-xs text-indigo-700">Drafted by AI. Review and edit before saving.</p>
              ) : null}
              {draftError ? <p className="text-xs font-medium text-rose-700">{draftError}</p> : null}
            </div>
          ) : null}

          <Field label="Overview" error={errors.job_overview} required>
            <Textarea
              value={values.job_overview}
              onChange={(e) => set("job_overview", e.target.value)}
              rows={4}
              placeholder="What this person will work on and why the role exists."
              aria-invalid={!!errors.job_overview}
            />
          </Field>

          <Field
            label="Required qualifications"
            error={errors.required_qualifications}
            required
          >
            <Textarea
              value={values.required_qualifications}
              onChange={(e) => set("required_qualifications", e.target.value)}
              rows={4}
              placeholder="Experience, education, and must-haves."
              aria-invalid={!!errors.required_qualifications}
            />
          </Field>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="space-y-5 p-6">
          <div>
            <h2 className="text-sm font-semibold text-slate-800">Requirements</h2>
            <p className="mt-0.5 text-xs text-slate-500">
              Missing one must-have caps a candidate&apos;s score at 70, and missing two or more
              caps it at 50. Capped candidates are flagged with the reason, never rejected. Years
              and education only count for candidates whose resume records them.
            </p>
          </div>

          <Field
            label="Must-have skills"
            error={errors.must_have_skills}
            hint="Press Enter or comma after each skill. A close variant counts as a match."
            group
          >
            <SkillChips
              label="Must-have skills"
              value={values.must_have_skills}
              other={values.nice_to_have_skills}
              onChange={(next) => set("must_have_skills", next)}
              placeholder="Python, SQL"
            />
          </Field>

          <Field
            label="Nice-to-have skills"
            error={errors.nice_to_have_skills}
            hint="Each one a candidate has adds to their skill score, up to 10 points."
            group
          >
            <SkillChips
              label="Nice-to-have skills"
              value={values.nice_to_have_skills}
              other={values.must_have_skills}
              onChange={(next) => set("nice_to_have_skills", next)}
              placeholder="dbt, Spark"
            />
          </Field>

          <div className="grid gap-5 sm:grid-cols-2">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Min years" error={errors.min_years}>
                <Input
                  inputMode="numeric"
                  value={values.min_years}
                  onChange={(e) => set("min_years", e.target.value)}
                  placeholder="3"
                  aria-invalid={!!errors.min_years}
                />
              </Field>
              <Field label="Max years" error={errors.max_years}>
                <Input
                  inputMode="numeric"
                  value={values.max_years}
                  onChange={(e) => set("max_years", e.target.value)}
                  placeholder="8"
                  aria-invalid={!!errors.max_years}
                />
              </Field>
            </div>

            <Field label="Minimum education">
              <Choice
                value={values.min_education}
                onChange={(v) => set("min_education", v)}
                options={EDUCATION_LEVELS}
                label="Minimum education"
              />
            </Field>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="space-y-5 p-6">
          <h2 className="text-sm font-semibold text-slate-800">Where and how</h2>

          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Status" hint="Only open roles are matched to candidates.">
              <Choice
                value={values.status}
                onChange={(v) => set("status", v)}
                options={JOB_STATUSES}
                label="Status"
              />
            </Field>

            <Field label="Location">
              <Input
                value={values.location}
                onChange={(e) => set("location", e.target.value)}
                placeholder="Austin, TX"
              />
            </Field>

            <Field label="Location type">
              <Choice
                value={values.location_type}
                onChange={(v) => set("location_type", v)}
                options={LOCATION_TYPES}
                label="Location type"
              />
            </Field>

            <Field label="Job type">
              <Choice
                value={values.job_type}
                onChange={(v) => set("job_type", v)}
                options={JOB_TYPES}
                label="Job type"
              />
            </Field>

            <Field label="Experience level">
              <Choice
                value={values.experience_level}
                onChange={(v) => set("experience_level", v)}
                options={EXPERIENCE_LEVELS}
                label="Experience level"
              />
            </Field>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Min salary" error={errors.min_salary}>
                <Input
                  inputMode="numeric"
                  value={values.min_salary}
                  onChange={(e) => set("min_salary", e.target.value)}
                  placeholder="150000"
                  aria-invalid={!!errors.min_salary}
                />
              </Field>
              <Field label="Max salary" error={errors.max_salary}>
                <Input
                  inputMode="numeric"
                  value={values.max_salary}
                  onChange={(e) => set("max_salary", e.target.value)}
                  placeholder="200000"
                  aria-invalid={!!errors.max_salary}
                />
              </Field>
            </div>
          </div>

          <div className="border-t border-slate-100 pt-4">
            <button
              type="button"
              onClick={() => setShowMore((open) => !open)}
              className="flex items-center gap-1.5 text-sm font-medium text-slate-600 hover:text-slate-900"
              aria-expanded={showMore}
            >
              <ChevronDown
                className={cn("h-4 w-4 transition-transform", showMore && "rotate-180")}
                aria-hidden
              />
              More details
            </button>

            {showMore ? (
              <div className="mt-4 grid gap-5 sm:grid-cols-2">
                <Field label="Hiring manager">
                  <Input
                    value={values.hiring_manager}
                    onChange={(e) => set("hiring_manager", e.target.value)}
                  />
                </Field>
                <Field label="Recruiter">
                  <Input
                    value={values.recruiter}
                    onChange={(e) => set("recruiter", e.target.value)}
                  />
                </Field>
                <Field label="Application deadline">
                  <Input
                    type="date"
                    value={values.application_deadline}
                    onChange={(e) => set("application_deadline", e.target.value)}
                  />
                </Field>
                <Field label="Start date">
                  <Input
                    type="date"
                    value={values.start_date}
                    onChange={(e) => set("start_date", e.target.value)}
                  />
                </Field>
              </div>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {formError ? (
        <p
          role="alert"
          className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700"
        >
          {formError}
        </p>
      ) : null}

      <div className="flex items-center gap-3">
        <Button type="submit" disabled={busy}>
          {busy ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
          ) : (
            <Save className="mr-2 h-4 w-4" aria-hidden />
          )}
          {editing ? "Save changes" : "Create job"}
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={busy}
          onClick={() => router.back()}
        >
          Cancel
        </Button>
      </div>
    </form>
  );
}

function Field({
  label,
  error,
  hint,
  required,
  group,
  children,
}: {
  label: string;
  error?: string;
  hint?: string;
  required?: boolean;
  /** A div instead of a label, for controls holding buttons: clicking a
      label activates its first button, which would remove a chip. */
  group?: boolean;
  children: React.ReactNode;
}) {
  const Wrapper = group ? "div" : "label";
  return (
    <Wrapper className="block text-sm">
      <span className="mb-1 block font-medium text-slate-700">
        {label}
        {required ? null : <span className="font-normal text-slate-400"> (optional)</span>}
      </span>
      {children}
      {error ? (
        <span className="mt-1 block text-xs text-rose-600">{error}</span>
      ) : hint ? (
        <span className="mt-1 block text-xs text-slate-500">{hint}</span>
      ) : null}
    </Wrapper>
  );
}

/** A list of skills as removable chips with a free-text input at the end. */
function SkillChips({
  label,
  value,
  other,
  onChange,
  placeholder,
}: {
  label: string;
  value: string[];
  /** The opposite list: a skill cannot be both a must-have and a nice-to-have. */
  other: string[];
  onChange: (next: string[]) => void;
  placeholder: string;
}) {
  const [draft, setDraft] = useState("");

  function commit() {
    if (!draft.trim()) return;
    onChange(addSkills(value, draft, other));
    setDraft("");
  }

  return (
    <div className="flex min-h-10 flex-wrap items-center gap-1.5 rounded-md border border-input bg-white px-2 py-1.5 focus-within:ring-2 focus-within:ring-indigo-200">
      {value.map((skill) => (
        <span
          key={skill}
          className="inline-flex items-center gap-1 rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-700"
        >
          {skill}
          <button
            type="button"
            onClick={() => onChange(value.filter((s) => s !== skill))}
            className="text-slate-400 hover:text-slate-700"
            aria-label={`Remove ${skill}`}
          >
            <X className="h-3 w-3" aria-hidden />
          </button>
        </span>
      ))}
      <input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === ",") {
            e.preventDefault();
            commit();
          } else if (e.key === "Backspace" && !draft && value.length) {
            onChange(value.slice(0, -1));
          }
        }}
        onBlur={commit}
        aria-label={label}
        placeholder={value.length ? "" : placeholder}
        className="min-w-32 flex-1 bg-transparent py-0.5 text-sm outline-none placeholder:text-slate-400"
      />
    </div>
  );
}

function Choice({
  value,
  onChange,
  options,
  label,
}: {
  value: string;
  onChange: (value: string) => void;
  options: readonly { value: string; label: string }[];
  label: string;
}) {
  const current = options.find((option) => option.value === value);
  return (
    // Base UI types the change value as nullable (a Select can be cleared).
    // These are always-set enums, so a null is treated as "no change".
    <Select value={value} onValueChange={(next) => onChange(next ?? value)}>
      <SelectTrigger className="h-10 w-full bg-white" aria-label={label}>
        <SelectValue>{current?.label ?? "Choose…"}</SelectValue>
      </SelectTrigger>
      <SelectContent>
        {options.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

/** FastAPI puts a string in `detail` for our errors and an array for 422s. */
function readDetail(payload: { detail?: unknown } | null): string | null {
  const detail = payload?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const first = detail[0] as { msg?: string; loc?: unknown[] } | undefined;
    if (first?.msg) {
      const field = Array.isArray(first.loc) ? first.loc[first.loc.length - 1] : null;
      return field ? `${String(field)}: ${first.msg}` : first.msg;
    }
  }
  return null;
}
