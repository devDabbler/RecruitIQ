/**
 * The shape of the job create/edit form, kept out of the component so the
 * validation is testable without rendering anything.
 *
 * The option lists mirror the enums in backend/models/job.py. They are written
 * out rather than derived from `schema.d.ts` because the generated types give
 * us the *values* but not the human labels, and the display order here is a
 * deliberate choice (most common first) rather than the enum's order.
 */
import type { Job } from "./domain";

export const JOB_STATUSES = [
  { value: "draft", label: "Draft" },
  { value: "open", label: "Open" },
  { value: "on_hold", label: "On hold" },
  { value: "filled", label: "Filled" },
  { value: "closed", label: "Closed" },
  { value: "cancelled", label: "Cancelled" },
] as const;

export const JOB_TYPES = [
  { value: "full_time", label: "Full time" },
  { value: "part_time", label: "Part time" },
  { value: "contract", label: "Contract" },
  { value: "temporary", label: "Temporary" },
  { value: "internship", label: "Internship" },
  { value: "freelance", label: "Freelance" },
] as const;

export const LOCATION_TYPES = [
  { value: "on_site", label: "On site" },
  { value: "remote", label: "Remote" },
  { value: "hybrid", label: "Hybrid" },
] as const;

export const EXPERIENCE_LEVELS = [
  { value: "entry", label: "Entry" },
  { value: "mid", label: "Mid" },
  { value: "senior", label: "Senior" },
  { value: "lead", label: "Lead" },
  { value: "executive", label: "Executive" },
] as const;

/** Mirrors JobRequirements in backend/services/job_requirements.py. */
export const EDUCATION_LEVELS = [
  { value: "none", label: "No minimum" },
  { value: "bachelor", label: "Bachelor's degree" },
  { value: "master", label: "Master's degree" },
  { value: "phd", label: "PhD" },
] as const;

export const MAX_REQUIREMENT_SKILLS = 20;
export const MAX_SKILL_LENGTH = 60;

export interface JobFormValues {
  title: string;
  department: string;
  job_overview: string;
  required_qualifications: string;
  skills: string;
  status: string;
  location: string;
  location_type: string;
  job_type: string;
  experience_level: string;
  min_salary: string;
  max_salary: string;
  hiring_manager: string;
  recruiter: string;
  application_deadline: string;
  start_date: string;
  /** Track 2 Phase 1: structured requirements. */
  must_have_skills: string[];
  nice_to_have_skills: string[];
  min_years: string;
  max_years: string;
  min_education: string;
}

export const EMPTY_JOB: JobFormValues = {
  title: "",
  department: "",
  job_overview: "",
  required_qualifications: "",
  skills: "",
  status: "draft",
  location: "",
  location_type: "on_site",
  job_type: "full_time",
  experience_level: "mid",
  min_salary: "",
  max_salary: "",
  hiring_manager: "",
  recruiter: "",
  application_deadline: "",
  start_date: "",
  must_have_skills: [],
  nice_to_have_skills: [],
  min_years: "",
  max_years: "",
  min_education: "none",
};

/** Turn an API job into form values. Every field becomes a string. */
export function jobToFormValues(job: Job): JobFormValues {
  return {
    title: job.title ?? "",
    department: job.department ?? "",
    job_overview: job.job_overview ?? "",
    required_qualifications: job.required_qualifications ?? "",
    skills: (job.skills ?? []).join(", "),
    status: job.status ?? "draft",
    location: job.location ?? "",
    location_type: job.location_type ?? "on_site",
    job_type: job.job_type ?? "full_time",
    experience_level: job.experience_level ?? "mid",
    min_salary: job.min_salary == null ? "" : String(job.min_salary),
    max_salary: job.max_salary == null ? "" : String(job.max_salary),
    hiring_manager: job.hiring_manager ?? "",
    recruiter: job.recruiter ?? "",
    // <input type="date"> wants YYYY-MM-DD; the API sends a full timestamp.
    application_deadline: (job.application_deadline ?? "").slice(0, 10),
    start_date: (job.start_date ?? "").slice(0, 10),
    must_have_skills: [...(job.requirements?.must_have_skills ?? [])],
    nice_to_have_skills: [...(job.requirements?.nice_to_have_skills ?? [])],
    min_years: job.requirements?.min_years == null ? "" : String(job.requirements.min_years),
    max_years: job.requirements?.max_years == null ? "" : String(job.requirements.max_years),
    min_education: job.requirements?.min_education ?? "none",
  };
}

/**
 * Add a typed skill to a chip list. Commas split several at once; blanks,
 * case-insensitive duplicates, and anything already in `other` (the opposite
 * list) are skipped. Returns the list unchanged when nothing was added.
 */
export function addSkills(list: string[], typed: string, other: string[] = []): string[] {
  const taken = new Set([...list, ...other].map((s) => s.toLowerCase()));
  const next = [...list];
  for (const raw of typed.split(",")) {
    const skill = raw.replace(/\s+/g, " ").trim();
    if (!skill || taken.has(skill.toLowerCase())) continue;
    taken.add(skill.toLowerCase());
    next.push(skill);
  }
  return next.length === list.length ? list : next;
}

export type FieldErrors = Partial<Record<keyof JobFormValues, string>>;

/**
 * Validate before sending.
 *
 * The four required fields are non-optional in `JobCreateUpdate`, so omitting
 * one is a 422 from FastAPI with a body the form would have to decode. Checking
 * here turns that into an inline message on the offending field.
 */
export function validateJob(values: JobFormValues): FieldErrors {
  const errors: FieldErrors = {};

  if (!values.title.trim()) errors.title = "A title is required.";
  if (!values.department.trim()) errors.department = "A department is required.";
  if (!values.job_overview.trim()) errors.job_overview = "An overview is required.";
  if (!values.required_qualifications.trim()) {
    errors.required_qualifications = "Required qualifications cannot be empty.";
  }

  const min = values.min_salary.trim() === "" ? null : Number(values.min_salary);
  const max = values.max_salary.trim() === "" ? null : Number(values.max_salary);

  if (min !== null && (!Number.isFinite(min) || min < 0)) {
    errors.min_salary = "Enter a whole number, or leave it blank.";
  }
  if (max !== null && (!Number.isFinite(max) || max < 0)) {
    errors.max_salary = "Enter a whole number, or leave it blank.";
  }
  if (
    min !== null &&
    max !== null &&
    Number.isFinite(min) &&
    Number.isFinite(max) &&
    min > max
  ) {
    errors.max_salary = "The maximum cannot be below the minimum.";
  }

  const years = (value: string) => (value.trim() === "" ? null : Number(value));
  const minYears = years(values.min_years);
  const maxYears = years(values.max_years);
  const badYears = (n: number | null) => n !== null && (!Number.isInteger(n) || n < 0 || n > 50);
  if (badYears(minYears)) errors.min_years = "Enter whole years from 0 to 50, or leave it blank.";
  if (badYears(maxYears)) errors.max_years = "Enter whole years from 0 to 50, or leave it blank.";
  if (!errors.min_years && !errors.max_years && minYears !== null && maxYears !== null && minYears > maxYears) {
    errors.max_years = "The maximum cannot be below the minimum.";
  }

  for (const key of ["must_have_skills", "nice_to_have_skills"] as const) {
    if (values[key].length > MAX_REQUIREMENT_SKILLS) {
      errors[key] = `At most ${MAX_REQUIREMENT_SKILLS} skills.`;
    } else if (values[key].some((skill) => skill.length > MAX_SKILL_LENGTH)) {
      errors[key] = `Keep each skill under ${MAX_SKILL_LENGTH} characters.`;
    }
  }

  return errors;
}

/**
 * Form values to the JSON body `JobCreateUpdate` expects.
 *
 * Blank optional text becomes null rather than "", so an unfilled field reads
 * as absent in the database instead of as an empty string that then renders as
 * a stray separator on the job card.
 */
export function toJobPayload(values: JobFormValues): Record<string, unknown> {
  const orNull = (value: string) => (value.trim() === "" ? null : value.trim());
  const orNullNumber = (value: string) =>
    value.trim() === "" ? null : Math.trunc(Number(value));
  // The API takes full timestamps; <input type="date"> gives a bare date.
  const orNullDate = (value: string) =>
    value.trim() === "" ? null : `${value}T00:00:00`;

  return {
    title: values.title.trim(),
    department: values.department.trim(),
    job_overview: values.job_overview.trim(),
    required_qualifications: values.required_qualifications.trim(),
    skills: values.skills
      .split(",")
      .map((skill) => skill.trim())
      .filter(Boolean),
    status: values.status,
    location: orNull(values.location),
    location_type: values.location_type,
    job_type: values.job_type,
    experience_level: values.experience_level,
    min_salary: orNullNumber(values.min_salary),
    max_salary: orNullNumber(values.max_salary),
    hiring_manager: orNull(values.hiring_manager),
    recruiter: orNull(values.recruiter),
    application_deadline: orNullDate(values.application_deadline),
    start_date: orNullDate(values.start_date),
    requirements: {
      must_have_skills: values.must_have_skills,
      nice_to_have_skills: values.nice_to_have_skills,
      min_years: orNullNumber(values.min_years),
      max_years: orNullNumber(values.max_years),
      min_education: values.min_education === "none" ? null : values.min_education || null,
    },
  };
}

/**
 * "Start from an existing job" (ATS Phase E): the same role, as a new draft.
 * Dates are cleared because they almost never carry over.
 */
export function copyJobValues(job: Job): JobFormValues {
  return { ...jobToFormValues(job), status: "draft", application_deadline: "", start_date: "" };
}

export interface DescriptionDraft {
  job_overview: string;
  required_qualifications: string;
}

/** The only fields sent for an AI draft. No free text, no candidate data. */
export function draftRequestFrom(values: JobFormValues) {
  return {
    title: values.title.trim(),
    department: values.department.trim() || null,
    experience_level: values.experience_level || null,
    location_type: values.location_type || null,
    skills: values.skills
      .split(",")
      .map((skill) => skill.trim())
      .filter(Boolean),
  };
}

export function canRequestDraft(values: JobFormValues): boolean {
  return values.title.trim().length > 0;
}

export function hasWrittenDescription(values: JobFormValues): boolean {
  return Boolean(values.job_overview.trim() || values.required_qualifications.trim());
}

export function applyDraft(values: JobFormValues, draft: DescriptionDraft): JobFormValues {
  return {
    ...values,
    job_overview: draft.job_overview,
    required_qualifications: draft.required_qualifications,
  };
}

/** "3+ years", "2 to 5 years", "Up to 3 years", or null when no range is set. */
export function yearsLabel(min?: number | null, max?: number | null): string | null {
  if (min != null && max != null) return min === max ? `${min} years` : `${min} to ${max} years`;
  if (min != null) return `${min}+ years`;
  if (max != null) return `Up to ${max} years`;
  return null;
}

/** "Master's degree or higher", or null when there is no minimum. */
export function educationLabel(level?: string | null): string | null {
  const found = EDUCATION_LEVELS.find((option) => option.value === level);
  if (!found || found.value === "none") return null;
  return found.value === "phd" ? "PhD" : `${found.label} or higher`;
}
