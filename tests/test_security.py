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


def test_forwarded_header_is_ignored_from_untrusted_client(monkeypatch):
    from ratelimit import resolve_client_key

    monkeypatch.setenv("TRUSTED_PROXY_HOSTS", "10.0.0.0/8")

    assert resolve_client_key("203.0.113.5", "1.2.3.4") == "203.0.113.5"
    assert resolve_client_key(None, "1.2.3.4") == "unknown"


def test_forwarded_header_is_used_from_trusted_proxy(monkeypatch):
    from ratelimit import resolve_client_key

    monkeypatch.setenv("TRUSTED_PROXY_HOSTS", "10.0.0.0/8")

    assert resolve_client_key("10.0.0.1", "203.0.113.9, 10.0.0.1") == "203.0.113.9"


def test_spoofed_forwarded_header_cannot_bypass_login_limit(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_PER_MINUTE", "1")
    monkeypatch.setenv("TRUSTED_PROXY_HOSTS", "10.0.0.0/8")

    body = {"email": "spoof@example.com", "password": "wrong"}
    client.post("/users/login", json=body, headers={"X-Forwarded-For": "1.1.1.1"})
    response = client.post(
        "/users/login", json=body, headers={"X-Forwarded-For": "2.2.2.2"}
    )

    assert response.status_code == 429


def test_limiter_bounds_memory():
    from ratelimit import SlidingWindowLimiter

    limiter = SlidingWindowLimiter(max_entries=3)
    for index in range(10):
        limiter.check(f"client-{index}", 5, 60)

    assert len(limiter._buckets) <= 3


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
