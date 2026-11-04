"""Create a one-time tenant signup invite.

Usage:
    python -m scripts.create_tenant_invite
    python -m scripts.create_tenant_invite --description "Acme pilot" --days 14
    python -m scripts.create_tenant_invite --days 0 --description "Never expires"

The plaintext invite is printed once. Only its hash is stored.
"""

from __future__ import annotations

import argparse

from database import SessionLocal
from services.signup_invites import create_tenant_invite


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a one-time NEXA tenant invite.")
    parser.add_argument(
        "--description",
        default=None,
        help="Internal label for the invite, e.g. 'Acme pilot'.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Days until expiry. Use 0 for no expiry. Defaults to 7.",
    )
    args = parser.parse_args()

    if args.days < 0:
        parser.error("--days must be non-negative.")

    expires_in_days = None if args.days == 0 else args.days
    db = SessionLocal()
    try:
        _invite, code = create_tenant_invite(
            db,
            description=args.description,
            expires_in_days=expires_in_days,
        )
    finally:
        db.close()

    print("Tenant signup invite created. Store this now; it will not be shown again:")
    print(code)
    if expires_in_days is None:
        print("This invite does not expire. It can be used exactly once.")
    else:
        print(f"This invite expires in {expires_in_days} day(s).")


if __name__ == "__main__":
    main()
