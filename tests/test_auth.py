from __future__ import annotations

import uuid

from models import Tenant, User


def test_tenant_onboarding_and_login(client):
    suffix = uuid.uuid4().hex[:10]
    email = f"owner_{suffix}@example.com"
    password = "OwnerPass123!"

    created = client.post(
        "/tenants",
        json={
            "name": f"Owner Tenant {suffix}",
            "description": "auth test",
            "admin_email": email,
            "admin_password": password,
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["tenant"]["name"] == f"Owner Tenant {suffix}"
    assert body["admin_user"]["email"] == email
    assert body["roles_seeded"] == ["admin", "member"]

    login = client.post("/users/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    assert login.json()["user"]["role"] == "admin"

    profile = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert profile.status_code == 200
    assert profile.json()["email"] == email
    assert profile.json()["tenant_id"] == body["tenant"]["id"]


def test_login_is_email_case_insensitive(client, tenant):
    response = client.post(
        "/users/login",
        json={"email": tenant["email"].upper(), "password": tenant["password"]},
    )
    assert response.status_code == 200, response.text


def test_login_rejects_bad_credentials(client, tenant):
    wrong_password = client.post(
        "/users/login",
        json={"email": tenant["email"], "password": "not-the-password"},
    )
    assert wrong_password.status_code == 401

    unknown_user = client.post(
        "/users/login",
        json={"email": "missing@example.com", "password": "whatever"},
    )
    assert unknown_user.status_code == 401


def test_protected_route_requires_a_valid_token(client):
    missing = client.get("/users/me")
    assert missing.status_code == 401

    invalid = client.get(
        "/users/me",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert invalid.status_code == 401


def test_duplicate_admin_email_is_rejected(client, tenant):
    response = client.post(
        "/tenants",
        json={
            "name": "Duplicate Email Tenant",
            "admin_email": tenant["email"],
            "admin_password": "AnotherPass123!",
        },
    )
    assert response.status_code == 409, response.text


def test_tenant_can_be_created_without_an_admin(client):
    suffix = uuid.uuid4().hex[:10]
    response = client.post(
        "/tenants",
        json={"name": f"No Admin {suffix}", "description": "no admin"},
    )
    assert response.status_code == 201, response.text
    assert "admin_user" not in response.json()


def test_unknown_role_is_rejected(client, tenant):
    response = client.post(
        "/users",
        headers=tenant["headers"],
        json={
            "email": f"unknown_{uuid.uuid4().hex[:8]}@example.com",
            "password": "MemberPass123!",
            "role": "not-a-role",
        },
    )
    assert response.status_code == 400, response.text


def test_users_are_scoped_to_the_current_tenant(client, tenant, tenant_factory):
    other = tenant_factory("other")

    response = client.post(
        "/users",
        headers=tenant["headers"],
        json={
            "email": f"scoped_{uuid.uuid4().hex[:8]}@example.com",
            "password": "MemberPass123!",
            "role": "member",
        },
    )
    assert response.status_code == 201

    current_users = client.get("/users", headers=tenant["headers"])
    other_users = client.get("/users", headers=other["headers"])
    assert current_users.status_code == 200
    assert other_users.status_code == 200
    assert all(user["tenant_id"] == tenant["id"] for user in current_users.json()["users"])
    assert all(user["tenant_id"] == other["id"] for user in other_users.json()["users"])


def test_duplicate_user_email_is_rejected(client, tenant):
    email = f"duplicate_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "email": email,
        "password": "MemberPass123!",
        "role": "member",
    }

    first = client.post("/users", headers=tenant["headers"], json=payload)
    second = client.post("/users", headers=tenant["headers"], json=payload)
    assert first.status_code == 201
    assert second.status_code == 409


def test_deleted_user_does_not_delete_the_tenant(client, tenant, db):
    user = db.query(User).filter(User.id == tenant["admin_id"]).one()
    db.delete(user)
    db.commit()

    db.expire_all()
    assert db.query(Tenant).filter(Tenant.id == tenant["id"]).one_or_none() is not None
    assert db.query(User).filter(User.id == tenant["admin_id"]).first() is None
