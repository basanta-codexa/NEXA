"""Security middleware tests: headers, rate limiting, docs fallback."""

from __future__ import annotations

import pytest

from ratelimit import limiter


@pytest.fixture(autouse=True)
def reset_limiter():
    limiter.reset()
    yield
    limiter.reset()


def test_security_headers_on_health(client):
    response = client.get("/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "strict-origin" in response.headers["Referrer-Policy"]
    assert "max-age=31536000" in response.headers["Strict-Transport-Security"]
    # JSON endpoints get a strict CSP
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]


def test_docs_get_a_relaxed_csp(client):
    response = client.get("/docs")
    assert response.status_code == 200
    assert "cdn.jsdelivr.net" in response.headers["Content-Security-Policy"]


def test_rate_limit_login_returns_429(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_PER_MINUTE", "2")

    for _ in range(2):
        response = client.post("/users/login", json={"email": "x@example.com", "password": "pw"})
        assert response.status_code in (200, 401)

    response = client.post("/users/login", json={"email": "x@example.com", "password": "pw"})
    assert response.status_code == 429
    assert "Retry-After" in response.headers
    assert "Rate limit exceeded" in response.text


def test_rate_limit_signup_scoped_to_tenants(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_SIGNUP_PER_HOUR", "1")

    body = {
        "name": "Scoped Tenant",
        "description": "x",
        "admin_email": "a@example.com",
        "admin_password": "Password123!",
        "invite_code": "nxa_nonexistent_code",
    }
    first = client.post("/tenants", json=body)
    assert first.status_code == 403  # invalid invite — request happened

    second = client.post("/tenants", json=body)
    assert second.status_code == 429


def test_rate_limits_disabled_by_default(client):
    # conftest sets RATE_LIMIT_ENABLED=false for the suite
    for _ in range(5):
        response = client.post("/users/login", json={"email": "x@example.com", "password": "pw"})
        assert response.status_code != 429


def test_429_carries_ratelimit_headers(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_SIGNUP_PER_HOUR", "1")

    body = {
        "name": "Header Tenant",
        "description": "x",
        "admin_email": "b@example.com",
        "admin_password": "Password123!",
        "invite_code": "nxa_nonexistent",
    }
    client.post("/tenants", json=body)  # consumes the quota
    response = client.post("/tenants", json=body)
    assert response.status_code == 429
    assert response.headers["X-RateLimit-Limit"] == "1"
    assert response.headers["X-RateLimit-Remaining"] == "0"
