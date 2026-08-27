# Testing

```bash
poetry run pytest
```

## Current state

This suite was gitignored until 2026-08-27 — 138 test files existed on disk
and one was tracked. Un-ignoring them exposed real rot, which was triaged
rather than hidden:

- **Deleted:** six files defining `test_*` functions that took plain arguments
  (`pdf_path`, `text`, `resume_path`). pytest treated them as fixture requests
  and they errored at collection. They were written to be run by hand.
- **Deleted:** nine files plus six individual tests asserting on private
  methods and constructor kwargs that no longer exist
  (`RegexExtractor._clean_skill_name`, `NLPExtractor(llm_service=...)`).
  Testing private implementation details was the original mistake.
- **Skipped, with reasons:** tests needing the Nebius API (key returns HTTP 401
  and the provider is being replaced), a running server with seeded data, or a
  real resume fixture that policy forbids committing.

## Recently fixed

The nine failures left visible after Phase 0 were debugged and fixed in
Phase 1a. The suite is now 58 passed, 0 failed, 93 skipped. Root causes:

- **Character corruption in experience parsing** — encoding-corrupted
  regex character classes consumed a character after quotes:

  ```
  AssertionError: Expected 'Full Stack Developer', got 'Full Stack "eveloper'
  ```

- **Invented date precision** — date tokens were pushed through
  `dateutil.parse(fuzzy=True)` with no default, so a resume saying
  `2020 - Present` came back as `2020-08`, the missing month filled in
  from the wall clock. Dates are now preserved exactly as written.
- **Cache decorator contract drift** — `cache_result` required awaitable
  mocks the tests didn't provide; the decorator is await-compatible now.
- **Military dates** — only bare-year ranges matched, so
  `Jan 2015 - Jun 2019` produced an empty `start_date`.
- **Spaced LinkedIn URLs** — OCR output like `linked in.com/in/x` was
  missed entirely and mis-captured as a location.
- **Education section slicing** — the section ended at the first blank
  line (dropping every entry after the first) and institutions starting
  with the keyword ("University of California") never matched.
