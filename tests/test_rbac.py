from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from dependencies.permissions import Permissions
from models import Permission, Role, User
from security import hash_password
from services.rbac_service import seed_tenant_roles


def test_member_can_read_but_cannot_write(client, tenant, member_user):
    headers = member_user["headers"]

    assert client.get("/agents", headers=headers).status_code == 200
    assert client.get("/users", headers=headers).status_code == 200
    assert client.get("/documents", headers=headers).status_code == 200

    assert (
        client.post(
            "/agents",
            headers=headers,
            json={
                "name": "Member Agent",
                "role": "Support",
                "language": "English",
            },
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/users",
            headers=headers,
            json={
                "email": f"blocked_{uuid.uuid4().hex[:8]}@example.com",
                "password": "MemberPass123!",
                "role": "member",
            },
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/documents",
            headers=headers,
            json={"title": "Blocked", "content": "Should not be created."},
        ).status_code
        == 403
    )


def test_user_without_a_role_id_is_denied(client, tenant, db):
    email = f"norole_{uuid.uuid4().hex[:8]}@example.com"
    password = "NoRolePass123!"
    user = User(
        email=email,
        password_hash=hash_password(password),
        role="member",
        role_id=None,
        tenant_id=tenant["id"],
    )
    db.add(user)
    db.commit()

    login = client.post("/users/login", json={"email": email, "password": password})
    assert login.status_code == 200
    response = client.get(
        "/agents",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert response.status_code == 403
    assert "No role assigned" in response.json()["detail"]


def test_legacy_role_string_is_backfilled(tenant, db):
    email = f"legacy_{uuid.uuid4().hex[:8]}@example.com"
    user = User(
        email=email,
        password_hash=hash_password("LegacyPass123!"),
        role="member",
        role_id=None,
        tenant_id=tenant["id"],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    assert user.role_id is None

    seed_tenant_roles(db, tenant["id"])
    db.refresh(user)
    assert user.role_id is not None
    assert db.query(Role).filter(Role.id == user.role_id).one().name == "member"


def test_role_names_are_unique_per_tenant(tenant, db):
    duplicate = Role(name="member", tenant_id=tenant["id"])
    db.add(duplicate)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    assert (
        db.query(Role)
        .filter(Role.tenant_id == tenant["id"], Role.name == "member")
        .count()
        == 1
    )
