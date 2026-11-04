from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from models import Tenant, TenantSignupInvite
from services.signup_invites import create_tenant_invite


def _invite(db, description: str = "signup test") -> tuple[TenantSignupInvite, str]:
    return create_tenant_invite(
        db,
        description=description,
        expires_in_days=1,
    )


def test_missing_invite_code_is_rejected(client):
    response = client.post(
        "/tenants",
        json={"name": "Missing Invite Tenant"},
    )

    assert response.status_code == 422


def test_invalid_invite_code_is_rejected(client, db):
    response = client.post(
        "/tenants",
        json={
            "name": "Invalid Invite Tenant",
            "invite_code": "nxa_not-a-real-invite",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid or already-used invite code."
    assert db.query(Tenant).filter(Tenant.name == "Invalid Invite Tenant").count() == 0


def test_expired_invite_code_is_rejected(client, db):
    invite, code = _invite(db, "expired invite test")
    invite.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()

    response = client.post(
        "/tenants",
        json={"name": "Expired Invite Tenant", "invite_code": code},
    )

    assert response.status_code == 403
    db.refresh(invite)
    assert invite.used_at is None


def test_invite_code_can_be_used_exactly_once(client, db):
    suffix = uuid.uuid4().hex[:8]
    _invite_model, code = _invite(db, "one-time use test")

    first = client.post(
        "/tenants",
        json={"name": f"Invite Once {suffix}", "invite_code": code},
    )
    assert first.status_code == 201, first.text

    second = client.post(
        "/tenants",
        json={"name": f"Invite Again {suffix}", "invite_code": code},
    )
    assert second.status_code == 403

    db.expire_all()
    stored = db.query(TenantSignupInvite).filter_by(code_hash=stored_hash(code)).one()
    assert stored.used_at is not None


def test_failed_signup_does_not_burn_invite(client, tenant, db):
    suffix = uuid.uuid4().hex[:8]
    _invite_model, code = _invite(db, "rollback test")

    failed = client.post(
        "/tenants",
        json={
            "name": f"Rollback {suffix}",
            "admin_email": tenant["email"],
            "admin_password": "AnotherPass123!",
            "invite_code": code,
        },
    )
    assert failed.status_code == 409

    retried = client.post(
        "/tenants",
        json={
            "name": f"Rollback Retry {suffix}",
            "admin_email": f"rollback_{suffix}@example.com",
            "admin_password": "AnotherPass123!",
            "invite_code": code,
        },
    )
    assert retried.status_code == 201, retried.text


def test_invite_plaintext_is_not_stored(client, db):
    _invite_model, code = _invite(db, "no plaintext storage test")

    assert code.startswith("nxa_")
    assert all(invite.code_hash != code for invite in db.query(TenantSignupInvite))


def stored_hash(code: str) -> str:
    from services.signup_invites import hash_invite_code

    return hash_invite_code(code)
