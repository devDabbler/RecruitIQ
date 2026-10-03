"""Write web/src/lib/role-permissions.json from backend/utils/permissions.py.

    poetry run python scripts/export_permissions.py          # write it
    poetry run python scripts/export_permissions.py --check  # exit 1 if stale

The backend enforces the table; the web app reads this copy to decide which
controls to draw. One source, a generated copy, and a test
(test_permissions_json_is_current) that fails when they drift, the same
pattern as openapi.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import backend.utils.win_compat  # noqa: F401  (must precede deps needing pwd)

from backend.utils.permissions import ALL_PERMISSIONS, ROLE_LABELS, ROLE_PERMISSIONS

TARGET = Path(__file__).resolve().parents[1] / "web" / "src" / "lib" / "role-permissions.json"


def render() -> str:
    data = {
        "permissions": list(ALL_PERMISSIONS),
        "roles": {role: sorted(perms) for role, perms in sorted(ROLE_PERMISSIONS.items())},
        "labels": dict(sorted(ROLE_LABELS.items())),
    }
    return json.dumps(data, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 if the file is stale")
    args = parser.parse_args()
    expected = render()
    if args.check:
        current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
        if current != expected:
            print(f"{TARGET} is stale. Run: poetry run python scripts/export_permissions.py", file=sys.stderr)
            return 1
        print(f"{TARGET.name} is up to date")
        return 0
    TARGET.write_text(expected, encoding="utf-8", newline="\n")
    print(f"Wrote {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
