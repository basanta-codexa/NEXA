"""Shared pytest fixtures.

The suite runs against a disposable PostgreSQL database. It is created from the
same credentials as the development database, but with a unique name, so the
developer's ``nexa`` database is never touched.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load .env first, then force test-only settings before application modules
# import database.py, auth.py, or main.py.
load_dotenv(ROOT / ".env")

os.environ["JWT_SECRET_KEY"] = "nexa-test-secret-key-not-for-production"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["DB_POOL_SIZE"] = "2"
os.environ["DB_MAX_OVERFLOW"] = "0"
os.environ["LOG_LEVEL"] = "WARNING"
os.environ.setdefault("LIVEKIT_API_KEY", "test-key")
os.environ.setdefault("LIVEKIT_API_SECRET", "test-secret")


def _base_database_url() -> URL:
    explicit = os.getenv("DATABASE_URL")
    if explicit:
        return make_url(explicit)

    return URL.create(
        drivername="postgresql+psycopg2",
        username=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "nexa"),
    )


def _safe_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise RuntimeError(f"Unsafe PostgreSQL identifier: {value!r}")
    return value


_BASE_URL = _base_database_url()
_TEST_DB_NAME = _safe_identifier(
    os.getenv("TEST_DATABASE_NAME") or f"nexa_test_{uuid.uuid4().hex[:10]}"
)
_ADMIN_DB_NAME = _safe_identifier(os.getenv("TEST_ADMIN_DATABASE", "postgres"))
_TEST_URL = _BASE_URL.set(database=_TEST_DB_NAME)
_ADMIN_URL = _BASE_URL.set(database=_ADMIN_DB_NAME)

# database.py, alembic/env.py, and main.py all read this before connecting.
os.environ["DATABASE_URL"] = _TEST_URL.render_as_string(hide_password=False)


def _run_migrations() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env={**os.environ, "DATABASE_URL": os.environ["DATABASE_URL"]},
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Could not migrate the test database.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )


@pytest.fixture(scope="session", autouse=True)
def test_database():
    """Create, migrate, and remove a dedicated PostgreSQL database."""
    admin_engine = create_engine(
        _ADMIN_URL,
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
    )
    created = False

    try:
        with admin_engine.connect() as connection:
            connection.execute(
                text(f'DROP DATABASE IF EXISTS "{_TEST_DB_NAME}" WITH (FORCE)')
            )
            connection.execute(text(f'CREATE DATABASE "{_TEST_DB_NAME}"'))
        created = True

        _run_migrations()
        yield _TEST_DB_NAME
    finally:
        try:
            from database import engine

            engine.dispose()
        except Exception:
            pass

        if created:
            with admin_engine.connect() as connection:
                connection.execute(
                    text(f'DROP DATABASE IF EXISTS "{_TEST_DB_NAME}" WITH (FORCE)')
                )
        admin_engine.dispose()


@pytest.fixture(autouse=True)
def clean_database(test_database):
    """Reset all application tables after every test."""
    yield

    from database import engine

    statement = text(
        """
        TRUNCATE TABLE
            messages,
            conversations,
            document_chunks,
            documents,
            role_permissions,
            users,
            agents,
            roles,
            permissions,
            tenants
        RESTART IDENTITY CASCADE
        """
    )

    try:
        with engine.begin() as connection:
            connection.execute(statement)
    except Exception:
        # A failed test can leave a checked-out connection holding locks.
        engine.dispose()
        with engine.begin() as connection:
            connection.execute(statement)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db():
    from database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def tenant_factory(client, db):
    """Create a tenant plus its first admin and return login details."""
    password = "TestPass123!"

    def create(prefix: str = "tenant") -> dict:
        from services.signup_invites import create_tenant_invite

        suffix = uuid.uuid4().hex[:10]
        email = f"{prefix}_{suffix}@example.com"
        _invite, invite_code = create_tenant_invite(
            db,
            description=f"pytest invite for {prefix}",
            expires_in_days=1,
        )

        response = client.post(
            "/tenants",
            json={
                "name": f"{prefix.title()} {suffix}",
                "description": "pytest tenant",
                "admin_email": email,
                "admin_password": password,
                "invite_code": invite_code,
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()

        login = client.post(
            "/users/login",
            json={"email": email, "password": password},
        )
        assert login.status_code == 200, login.text
        token = login.json()["access_token"]

        return {
            "id": body["tenant"]["id"],
            "name": body["tenant"]["name"],
            "admin_id": body["admin_user"]["id"],
            "email": email,
            "password": password,
            "token": token,
            "headers": {"Authorization": f"Bearer {token}"},
        }

    return create


@pytest.fixture
def tenant(tenant_factory):
    return tenant_factory("tenant")


@pytest.fixture
def agent_factory(client, tenant):
    """Create an agent in the default test tenant."""
    def create(**overrides) -> dict:
        payload = {
            "name": "Test Agent",
            "role": "Support",
            "language": "English",
            "model_name": "fake",
        }
        payload.update(overrides)

        response = client.post(
            "/agents",
            headers=tenant["headers"],
            json=payload,
        )
        assert response.status_code == 200, response.text
        return response.json()

    return create


@pytest.fixture
def active_agent(client, tenant, agent_factory):
    agent = agent_factory()
    response = client.patch(
        f"/agents/{agent['id']}/status",
        headers=tenant["headers"],
        json={"status": "active"},
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def member_user(client, tenant):
    """Create and log in a member-role user in the default tenant."""
    email = f"member_{uuid.uuid4().hex[:10]}@example.com"
    password = "MemberPass123!"

    response = client.post(
        "/users",
        headers=tenant["headers"],
        json={"email": email, "password": password, "role": "member"},
    )
    assert response.status_code == 201, response.text

    login = client.post(
        "/users/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, login.text

    return {
        "id": response.json()["user"]["id"],
        "email": email,
        "password": password,
        "token": login.json()["access_token"],
        "headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
    }
