"""Write openapi.json from the FastAPI app, or check the committed copy is current.

The frontend's TypeScript types are generated from this file
(`openapi-typescript openapi.json`), so it is committed and CI asserts that
regenerating it produces no diff. Backend/frontend drift then fails the build
instead of a screen (Phase 3 spec §3).

    poetry run python scripts/export_openapi.py            # rewrite it
    poetry run python scripts/export_openapi.py --check     # fail if stale
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import backend.utils.win_compat  # noqa: F401  (must precede deps needing pwd)

from backend.main import app

OUTPUT = Path(__file__).resolve().parent.parent / "openapi.json"


def render() -> str:
    # sort_keys so the file is stable regardless of route registration order,
    # which is what makes the --check comparison meaningful.
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if the committed file differs from what the app emits",
    )
    args = parser.parse_args()

    current = render()

    if not args.check:
        OUTPUT.write_text(current, encoding="utf-8")
        print(f"Wrote {OUTPUT} ({len(current):,} bytes)")
        return 0

    if not OUTPUT.exists():
        print(f"{OUTPUT} is missing. Run: python scripts/export_openapi.py", file=sys.stderr)
        return 1

    if OUTPUT.read_text(encoding="utf-8") != current:
        print(
            f"{OUTPUT.name} is out of date with the API.\n"
            "Run: poetry run python scripts/export_openapi.py\n"
            "and commit the result, so the generated TypeScript client keeps up.",
            file=sys.stderr,
        )
        return 1

    print(f"{OUTPUT.name} is up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
