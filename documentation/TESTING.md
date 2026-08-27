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

## Tests that still fail

A handful fail against genuine defects and are deliberately left visible.
The clearest is a character-corruption bug in experience parsing:

```
AssertionError: Expected 'Full Stack Developer', got 'Full Stack "eveloper'
```

These are the eval harness's first targets.
