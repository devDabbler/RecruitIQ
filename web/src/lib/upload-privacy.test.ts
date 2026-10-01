import { describe, expect, it } from "vitest";

import type { UploadPrivacyReport } from "./domain";
import { privacySentence } from "./upload-privacy";

function report(overrides: Partial<UploadPrivacyReport> = {}): UploadPrivacyReport {
  return {
    identifying_fields_removed: ["name", "email", "phone", "linkedin"],
    name_mentions_scrubbed: 3,
    emails_scrubbed: 1,
    phones_scrubbed: 1,
    links_scrubbed: 2,
    model_calls_after_parse: 3,
    web_lookups: 0,
    ...overrides,
  };
}

describe("privacySentence", () => {
  it("names what was removed and scrubbed, then what saw the result", () => {
    expect(privacySentence(report())).toBe(
      "Before analysis, de-identification removed name, email, phone and LinkedIn and scrubbed " +
        "3 mentions of the name, 1 email, 1 phone number and 2 links from the text. " +
        "The 3 model calls that followed saw only that version, with no web lookup.",
    );
  });

  it("says so when there was nothing to remove", () => {
    const sentence = privacySentence(
      report({
        identifying_fields_removed: [],
        name_mentions_scrubbed: 0,
        emails_scrubbed: 0,
        phones_scrubbed: 0,
        links_scrubbed: 0,
        model_calls_after_parse: 2,
      }),
    );
    expect(sentence).toContain("found nothing identifying to remove");
    expect(sentence).toContain("The 2 model calls that followed");
  });

  it("singular forms read correctly", () => {
    const sentence = privacySentence(
      report({
        identifying_fields_removed: ["name"],
        name_mentions_scrubbed: 1,
        emails_scrubbed: 0,
        phones_scrubbed: 0,
        links_scrubbed: 1,
        model_calls_after_parse: 1,
      }),
    );
    expect(sentence).toContain("removed name and scrubbed 1 mention of the name and 1 link");
    expect(sentence).toContain("The 1 model call that followed");
  });

  it("is empty without a report (the direct parse path sends none)", () => {
    expect(privacySentence(null)).toBe("");
    expect(privacySentence(undefined)).toBe("");
  });

  it("never contains an em dash", () => {
    expect(privacySentence(report())).not.toContain("—");
  });
});
