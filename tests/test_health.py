from __future__ import annotations

import main


class _UnavailableDatabase:
    def connect(self):
        raise RuntimeError("database is down")


def test_root_and_health_endpoints(client):
    root = client.get("/")
    assert root.status_code == 200
    assert root.json()["service"] == "NEXA"

    for path in ("/health", "/ready"):
        response = client.get(path)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "ok"
        assert response.json()["database"] == "ok"


def test_health_is_503_when_database_is_unavailable(client, monkeypatch):
    monkeypatch.setattr(main, "engine", _UnavailableDatabase())

    for path in ("/health", "/ready"):
        response = client.get(path)
        assert response.status_code == 503, response.text
        assert response.json()["status"] == "degraded"
        assert response.json()["database"] == "unavailable"


def test_request_id_header_is_returned(client):
    response = client.get("/health", headers={"X-Request-ID": "pytest-request"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "pytest-request"
