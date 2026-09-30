/**
 * One readable sentence for any way an assistant request can fail.
 *
 * The chat bubble used to show whatever the response body was: nginx's 429 is
 * an HTML page, FastAPI's 422 is a JSON list of pydantic errors, and a crashed
 * turn was the raw exception text. None of that belongs in front of a visitor.
 */

export const TOO_MANY_REQUESTS_MESSAGE =
  "Too many requests right now. Please wait a minute and try again.";
export const TIMED_OUT_MESSAGE =
  "The assistant took too long to answer. Please try again, or ask a narrower question.";
export const UNAVAILABLE_MESSAGE =
  "The assistant is temporarily unavailable. Please try again in a moment.";
export const GENERIC_FAILURE_MESSAGE = "The assistant request failed. Please try again.";

/** Longest `detail` string we will show verbatim; anything longer is a dump, not a message. */
const MAX_DETAIL_CHARS = 300;

/**
 * The message to show for a non-OK response, given its status and body text.
 *
 * A short, plain `detail` string from our own backend or proxy is shown as is
 * (that is how "Live salary data is not connected" style copy gets through).
 * HTML, structured validation errors, and long bodies map to a generic line
 * by status.
 */
export function messageForFailedResponse(status: number, body: string): string {
  if (status === 429) return TOO_MANY_REQUESTS_MESSAGE;
  if (status === 504 || status === 408) return TIMED_OUT_MESSAGE;

  const detail = plainDetail(body);
  if (detail) return detail;

  if (status === 502 || status === 503) return UNAVAILABLE_MESSAGE;
  return GENERIC_FAILURE_MESSAGE;
}

/** The message for a fetch that threw rather than responded. */
export function messageForThrownError(error: unknown): string {
  if (error instanceof DOMException && error.name === "AbortError") return TIMED_OUT_MESSAGE;
  if (error instanceof Error && error.name === "AbortError") return TIMED_OUT_MESSAGE;
  return UNAVAILABLE_MESSAGE;
}

function plainDetail(body: string): string | null {
  const trimmed = body.trim();
  if (!trimmed || trimmed.startsWith("<")) return null;
  let detail: unknown;
  try {
    detail = (JSON.parse(trimmed) as { detail?: unknown }).detail;
  } catch {
    return null;
  }
  if (typeof detail !== "string") return null;
  const text = detail.trim();
  if (!text || text.startsWith("<") || text.length > MAX_DETAIL_CHARS) return null;
  return text;
}
