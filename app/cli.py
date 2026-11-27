"""Admin command line.

python -m app.cli create-user --email you@example.com --name "Dr You" --role admin
"""

import argparse
import getpass
import sys

from app.db.session import SessionLocal
from app.schemas.auth import UserCreate
from app.services import users


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-user", help="Create a clinician or admin account")
    create.add_argument("--email", required=True)
    create.add_argument("--name", required=True)
    create.add_argument("--role", choices=["clinician", "admin"], default="clinician")
    args = parser.parse_args(argv)

    password = getpass.getpass("Password (min 10 chars): ")
    if password != getpass.getpass("Repeat password: "):
        print("Passwords do not match.", file=sys.stderr)
        return 1
    payload = UserCreate(email=args.email, full_name=args.name, password=password, role=args.role)
    with SessionLocal() as db:
        try:
            user = users.create_user(db, **payload.model_dump())
        except users.DuplicateUserError as error:
            print(error, file=sys.stderr)
            return 1
    print(f"Created {user.role} {user.email} (id {user.id}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
