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
  };
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
  };
}
