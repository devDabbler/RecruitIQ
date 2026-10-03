/** Vocabulary for the candidate-facing status page (ATS Phase E). */
import type { PublicStatus } from "./domain";

export const PUBLIC_STATE_LABELS: Record<string, string> = {
  done: "Complete",
  current: "In progress",
  upcoming: "Coming up",
  closed: "Closed",
};

export function greeting(firstName: string | null | undefined): string {
  const name = firstName?.trim();
  return name ? `Hi ${name},` : "Hello,";
}

export function currentStageName(status: PublicStatus): string | null {
  return status.stages.find((stage) => stage.state === "current")?.name ?? null;
}

/** Status tokens are 32 URL-safe characters; anything else is not worth a request. */
const TOKEN_SHAPE = /^[A-Za-z0-9_-]{16,64}$/;

export function looksLikeToken(value: string): boolean {
  return TOKEN_SHAPE.test(value);
}
