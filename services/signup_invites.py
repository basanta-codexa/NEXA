"""Tenant signup invite lifecycle.

Plaintext invite codes are never stored. Only their SHA-256 hashes are
persisted, and each code can be used exactly once. The calling transaction
is responsible for committing or rolling back ``used_at`` together with the
tenant being created.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import TenantSignupInvite

MAX_INVITE_CODE_LENGTH = 256


def hash_invite_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def create_tenant_invite(
    db: Session,
    *,
    description: str | None = None,
    expires_in_days: int | None = 7,
) -> tuple[TenantSignupInvite, str]:
    """Create an invite and return the model plus the only plaintext copy."""
    code = f"nxa_{secrets.token_urlsafe(32)}"
    now = datetime.now(timezone.utc)

    if expires_in_days is not None and expires_in_days < 0:
        raise ValueError("expires_in_days must be non-negative or None.")

    expires_at = (
        now + timedelta(days=expires_in_days)
        if expires_in_days is not None and expires_in_days > 0
        else None
    )

    invite = TenantSignupInvite(
        code_hash=hash_invite_code(code),
        description=description,
        expires_at=expires_at,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    return invite, code


def consume_tenant_invite(db: Session, invite_code: str) -> TenantSignupInvite:
    """Validate and mark an invite as used in the current transaction."""
    cleaned_code = (invite_code or "").strip()
    if not cleaned_code or len(cleaned_code) > MAX_INVITE_CODE_LENGTH:
        _invalid_invite()

    token_hash = hash_invite_code(cleaned_code)
    invite = (
        db.query(TenantSignupInvite)
        .filter(TenantSignupInvite.code_hash == token_hash)
        .with_for_update()
        .first()
    )

    now = datetime.now(timezone.utc)

    if (
        invite is None
        or invite.used_at is not None
        or (invite.expires_at is not None and invite.expires_at <= now)
    ):
        _invalid_invite()

    invite.used_at = now
    db.flush()
    return invite


def _invalid_invite() -> None:
    # Deliberately vague: don't reveal whether a code exists, was used, or expired.
    raise HTTPException(status_code=403, detail="Invalid or already-used invite code.")
