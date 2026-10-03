import "server-only";

import { redirect } from "next/navigation";

import { getUser } from "./session";

/**
 * Send an interviewer to their own home (ATS Phase B).
 *
 * The API already refuses interviewers on Matching, Upload, the assistant,
 * and the team list; this is the courtesy that keeps them from landing on a
 * page that can only show an error.
 */
export async function redirectInterviewer(to: string = "/interviews"): Promise<void> {
  const user = await getUser();
  if (user?.role === "interviewer") redirect(to);
}
