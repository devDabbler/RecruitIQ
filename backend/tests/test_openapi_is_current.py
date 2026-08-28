"""The committed openapi.json must match what the app emits.

The frontend's TypeScript types are generated from that file, so a route whose
shape changes without a regenerated schema produces a client that type-checks
against an API that no longer exists. Failing here is the cheap version of
finding out; a blank screen in the browser is the expensive one.
"""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "export_openapi.py"


def test_committed_openapi_matches_the_app():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
