from __future__ import annotations

import uuid

from dependencies.permissions import Permissions
from models import Permission, Role, User
from security import hash_password
from services.rbac_service import seed_tenant_roles


def _create_reader_user(client, db, tenant) -> dict:
    """Create a tenant user whose role has agent:read only."""
    seed_tenant_roles(db, tenant["id"])

    role = Role(name=f"reader_{uuid.uuid4().hex[:8]}", tenant_id=tenant["id"])
    db.add(role)
    db.flush()

    read_permission = db.query(Permission).filter(
        Permission.name == Permissions.AGENT_READ
    ).one()
    role.permissions = [read_permission]
    db.commit()

    email = f"reader_{uuid.uuid4().hex[:8]}@example.com"
    password = "ReaderPass123!"
    user = User(
        email=email,
        password_hash=hash_password(password),
        role=role.name,
        role_id=role.id,
        tenant_id=tenant["id"],
    )
    db.add(user)
    db.commit()

    login = client.post(
        "/users/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200

    return {
        "headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
        "role_id": role.id,
    }


def test_read_only_role_cannot_run_agents(client, tenant, active_agent, db):
    reader = _create_reader_user(client, db, tenant)

    response = client.post(
        f"/agents/{active_agent['id']}/run",
        headers=reader["headers"],
        json={"message": "hello"},
    )

    assert response.status_code == 403


def test_read_only_role_cannot_start_voice(client, tenant, active_agent, db):
    reader = _create_reader_user(client, db, tenant)

    response = client.post(
        f"/agents/{active_agent['id']}/voice/session",
        headers=reader["headers"],
        json={},
    )

    assert response.status_code == 403


def test_member_role_can_run_agent_with_explicit_permission(
    client,
    member_user,
    active_agent,
):
    response = client.post(
        f"/agents/{active_agent['id']}/run",
        headers=member_user["headers"],
        json={"message": "hello"},
    )

    assert response.status_code == 200
    assert response.json()["model"] == "fake"


def test_member_role_includes_run_and_voice_start(client, tenant, member_user, db):
    member_role = db.query(Role).filter(
        Role.tenant_id == tenant["id"],
        Role.name == "member",
    ).one()
    permission_names = {permission.name for permission in member_role.permissions}

    assert Permissions.AGENT_RUN in permission_names
    assert Permissions.VOICE_START in permission_names


def test_role_permissions_are_tenant_scoped(db, tenant):
    member_role = db.query(Role).filter(
        Role.tenant_id == tenant["id"],
        Role.name == "member",
    ).one()

    assert all(
        role.tenant_id == tenant["id"]
        for role in db.query(Role).filter(Role.id == member_role.id).all()
    )
