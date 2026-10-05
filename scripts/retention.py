"""Erase candidates inactive for longer than the retention window.

Pilot plan Track 1 #6. Run daily by deploy/recruitiq-retention.timer; also
safe to run by hand:

    poetry run python scripts/retention.py --dry-run
    poetry run python scripts/retention.py            # uses RETENTION_DAYS
    poetry run python scripts/retention.py --days 365

RETENTION_DAYS unset or 0 means retention is off and the script does
nothing. Erasing only happens with DEPLOYMENT_MODE=internal: the public demo
holds synthetic candidates whose seeded timelines age, and a timer must
never empty it. A dry run works in either mode.

Output names candidates by id only, never by name or email, because it ends
up in the systemd journal. The rules for what counts as activity and who is
held back are in backend/services/retention_service.py.
"""
from __future__ import annotations

import argparse
import logging
import sys

import backend.utils.win_compat  # noqa: F401  (must precede deps needing pwd)

from backend.services import retention_service
from backend.services.storage_service import StorageService
from backend.utils.config import get_settings
from backend.utils.database import SessionLocal


def resume_storage():
    """The store uploads go to: MinIO when reachable, else local files.

    Same choice ServiceRegistry.resume_service makes, without building the
    LLM and agent services that come with the registry.
    """
    try:
        from backend.services.minio_storage_service import MinioStorageService

        store = MinioStorageService()
        store._initialize_client()
        return store
    except Exception:
        return StorageService()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=None, help="override RETENTION_DAYS")
    parser.add_argument("--dry-run", action="store_true", help="list what would be erased; change nothing")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s", force=True)
    log = logging.getLogger("retention")
    settings = get_settings()

    days = args.days if args.days is not None else settings.retention_days
    if not days:
        log.info("retention is off (RETENTION_DAYS is unset or 0); nothing to do")
        return 0
    try:
        retention_service.check_days(days)
    except retention_service.RetentionConfigError as exc:
        log.error("%s", exc)
        return 2

    dry_run = args.dry_run
    if not settings.is_internal and not dry_run:
        log.warning(
            "DEPLOYMENT_MODE=%s holds the synthetic demo, so retention only reports; "
            "set DEPLOYMENT_MODE=internal to erase",
            settings.deployment_mode,
        )
        dry_run = True

    db = SessionLocal()
    try:
        report = retention_service.run_retention(
            db, days, dry_run=dry_run, storage=None if dry_run else resume_storage()
        )
    finally:
        db.close()

    for candidate in report.expired:
        state = "would erase" if dry_run else ("FAILED" if candidate.candidate_id in report.failed else "erased")
        log.info("%s %s (last activity %s)", state, candidate.candidate_id, candidate.last_activity)
    for candidate in report.held:
        log.info("held %s (%s, last activity %s)", candidate.candidate_id, candidate.held, candidate.last_activity)
    log.info("%s", report.summary())
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
