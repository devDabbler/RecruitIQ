import { describe, expect, it } from "vitest";

import {
  EMPTY_JOB,
  jobToFormValues,
  toJobPayload,
  validateJob,
  type JobFormValues,
} from "./job-form";
import type { Job } from "./domain";

function values(overrides: Partial<JobFormValues> = {}): JobFormValues {
  return {
    ...EMPTY_JOB,
    title: "Staff Engineer",
    department: "Engineering",
    job_overview: "Own the platform.",
    required_qualifications: "Kubernetes, 7+ years",
    ...overrides,
  };
}

describe("validateJob", () => {
  it("accepts a fully filled form", () => {
    expect(validateJob(values())).toEqual({});
  });

  it.each([
    ["title", "A title is required."],
    ["department", "A department is required."],
    ["job_overview", "An overview is required."],
    ["required_qualifications", "Required qualifications cannot be empty."],
  ])("requires %s", (field, message) => {
    const errors = validateJob(values({ [field]: "" } as Partial<JobFormValues>));
    expect(errors[field as keyof JobFormValues]).toBe(message);
  });

  it("treats whitespace as missing", () => {
    // FastAPI would accept "   " and store a job with a blank title, which then
    // matches nothing and reads as a broken row on the jobs page.
    expect(validateJob(values({ title: "   " })).title).toBeDefined();
  });

  it("allows blank salaries", () => {
    const errors = validateJob(values({ min_salary: "", max_salary: "" }));
    expect(errors.min_salary).toBeUndefined();
    expect(errors.max_salary).toBeUndefined();
  });

  it("rejects a maximum below the minimum", () => {
    const errors = validateJob(values({ min_salary: "200000", max_salary: "100000" }));
    expect(errors.max_salary).toBe("The maximum cannot be below the minimum.");
  });

  it("accepts a minimum equal to the maximum", () => {
    expect(validateJob(values({ min_salary: "150000", max_salary: "150000" }))).toEqual({});
  });

  it("rejects non-numeric and negative salaries", () => {
    expect(validateJob(values({ min_salary: "a lot" })).min_salary).toBeDefined();
    expect(validateJob(values({ max_salary: "-5" })).max_salary).toBeDefined();
  });
});

describe("toJobPayload", () => {
  it("splits skills into a trimmed list", () => {
    const payload = toJobPayload(values({ skills: "Python, SQL ,  dbt " }));
    expect(payload.skills).toEqual(["Python", "SQL", "dbt"]);
  });

  it("drops empty skill entries", () => {
    expect(toJobPayload(values({ skills: "Python,,  , SQL" })).skills).toEqual([
      "Python",
      "SQL",
    ]);
  });

  it("sends an empty list rather than nothing when no skills are given", () => {
    expect(toJobPayload(values({ skills: "" })).skills).toEqual([]);
  });

  it("turns blank optional text into null, not an empty string", () => {
    const payload = toJobPayload(values({ location: "", hiring_manager: "  " }));
    expect(payload.location).toBeNull();
    expect(payload.hiring_manager).toBeNull();
  });

  it("sends salaries as integers and blanks as null", () => {
    const payload = toJobPayload(values({ min_salary: "150000", max_salary: "" }));
    expect(payload.min_salary).toBe(150000);
    expect(payload.max_salary).toBeNull();
  });

  it("expands a date input into the timestamp the API expects", () => {
    const payload = toJobPayload(values({ start_date: "2026-09-01" }));
    expect(payload.start_date).toBe("2026-09-01T00:00:00");
  });

  it("trims the required text fields", () => {
    expect(toJobPayload(values({ title: "  Staff Engineer  " })).title).toBe(
      "Staff Engineer",
    );
  });
});

describe("jobToFormValues", () => {
  const job = {
    id: 7,
    title: "Senior Data Engineer",
    department: "Engineering",
    job_overview: "Own the pipeline.",
    required_qualifications: "Python, SQL",
    location: null,
    location_type: "remote",
    job_type: "full_time",
    experience_level: "senior",
    min_salary: 170000,
    max_salary: null,
    status: "open",
    hiring_manager: null,
    recruiter: null,
    application_deadline: "2026-10-01T00:00:00",
    start_date: null,
    views: 0,
    applications: 0,
    created_at: "2026-01-01T00:00:00",
    updated_at: "2026-01-01T00:00:00",
    job_metadata: {},
    skills: ["Python", "SQL"],
  } as unknown as Job;

  it("joins skills back into a comma-separated field", () => {
    expect(jobToFormValues(job).skills).toBe("Python, SQL");
  });

  it("renders nulls as empty strings so inputs stay controlled", () => {
    const form = jobToFormValues(job);
    expect(form.location).toBe("");
    expect(form.max_salary).toBe("");
    expect(form.start_date).toBe("");
  });

  it("truncates timestamps to the date an <input type=date> accepts", () => {
    expect(jobToFormValues(job).application_deadline).toBe("2026-10-01");
  });

  it("round-trips through the payload without losing the required fields", () => {
    const payload = toJobPayload(jobToFormValues(job));
    expect(payload.title).toBe("Senior Data Engineer");
    expect(payload.skills).toEqual(["Python", "SQL"]);
    expect(payload.min_salary).toBe(170000);
  });
});
