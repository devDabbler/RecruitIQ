/**
 * Wording the per-upload de-identification report as one sentence.
 *
 * Pure, so the upload screen's privacy line can be unit tested without
 * rendering. The report comes from the backend's `anonymize_parsed_resume`
 * and describes what was removed from *this* file before the post-parse
 * model calls ran.
 */
import type { UploadPrivacyReport } from "./domain";

const FIELD_WORDS: Record<string, string> = {
  name: "name",
  email: "email",
  phone: "phone",
  address: "address",
  location: "location",
  linkedin: "LinkedIn",
  github: "GitHub",
  website: "website",
};

function join(items: string[]): string {
  if (items.length <= 1) return items.join("");
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

export function privacySentence(report: UploadPrivacyReport | null | undefined): string {
  if (!report) return "";

  const removed = report.identifying_fields_removed.map((f) => FIELD_WORDS[f] ?? f);
  const scrubbed: string[] = [];
  if (report.name_mentions_scrubbed > 0) {
    scrubbed.push(`${plural(report.name_mentions_scrubbed, "mention")} of the name`);
  }
  if (report.emails_scrubbed > 0) scrubbed.push(plural(report.emails_scrubbed, "email"));
  if (report.phones_scrubbed > 0) scrubbed.push(plural(report.phones_scrubbed, "phone number"));
  if (report.links_scrubbed > 0) scrubbed.push(plural(report.links_scrubbed, "link"));

  const parts: string[] = [];
  if (removed.length) parts.push(`removed ${join(removed)}`);
  if (scrubbed.length) parts.push(`scrubbed ${join(scrubbed)} from the text`);

  const what = parts.length ? parts.join(" and ") : "found nothing identifying to remove";
  const calls = plural(report.model_calls_after_parse, "model call");
  const web = report.web_lookups === 0 ? "no web lookup" : plural(report.web_lookups, "web lookup");

  return `Before analysis, de-identification ${what}. The ${calls} that followed saw only that version, with ${web}.`;
}
