"""Create or update a staff account (admin by default).

There is no registration endpoint by design (Phase 3 spec §2), so this is how
an admin comes into existence, locally and on the droplet. ATS Phase B: it
also sets a password for anyone else, including the synthetic team the seed
creates without passwords.

    poetry run python scripts/create_admin.py --email you@example.com
    poetry run python scripts/create_admin.py --email marcus.webb@team.recruitiq.dev --role interviewer

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
from backend.utils.auth import ROLE_ADMIN, STAFF_ROLES, hash_password
from backend.utils.database import SessionLocal

MIN_PASSWORD_LENGTH = 12


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", default=ROLE_ADMIN, choices=STAFF_ROLES)
    parser.add_argument("--name", default=None, help="display name (optional)")
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
            user.role = args.role
            action = "Updated"
        else:
            user = User(email=args.email, hashed_password=hash_password(password), role=args.role)
            db.add(user)
            action = "Created"
        if args.name:
            user.name = args.name
        db.commit()
        print(f"{action} {args.role} {args.email}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
