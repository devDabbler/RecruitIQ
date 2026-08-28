"""Create or update the admin account.

There is no registration endpoint by design (Phase 3 spec §2), so this is how an
admin comes into existence — locally and on the droplet in Phase 4.

    poetry run python scripts/create_admin.py --email you@example.com

The password is read from the ADMIN_PASSWORD environment variable, or prompted
for without echo. Passing it on the command line is not supported: it would land
in shell history and in the process list.
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys

import backend.utils.win_compat  # noqa: F401  (must precede deps needing pwd)

from backend.models.models import User
from backend.utils.auth import ROLE_ADMIN, hash_password
from backend.utils.database import SessionLocal

MIN_PASSWORD_LENGTH = 12


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    args = parser.parse_args()

    password = os.environ.get("ADMIN_PASSWORD")
    if not password:
        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Confirm: "):
            print("Passwords did not match.", file=sys.stderr)
            return 1

    if len(password) < MIN_PASSWORD_LENGTH:
        print(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters.", file=sys.stderr
        )
        return 1

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == args.email).first()
        if user:
            user.hashed_password = hash_password(password)
            user.role = ROLE_ADMIN
            action = "Updated"
        else:
            user = User(
                email=args.email, hashed_password=hash_password(password), role=ROLE_ADMIN
            )
            db.add(user)
            action = "Created"
        db.commit()
        print(f"{action} admin {args.email}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
