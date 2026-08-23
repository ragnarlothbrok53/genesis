import pytest
from fastapi.testclient import TestClient

from genesis.core import debug_dashboard
from genesis.core.config import settings
from genesis.main import app


@pytest.fixture
def local_mode(monkeypatch):
    monkeypatch.setattr(settings, "CACHE_BACKEND", "embedded")
    debug_dashboard._requests.clear()
    yield
    debug_dashboard._requests.clear()


def test_middleware_captures_requests_in_local_mode(local_mode):
    client = TestClient(app)
    client.get("/api/health")

    captured = client.get("/api/_debug/requests").json()

    assert any(
        entry["method"] == "GET" and entry["path"] == "/api/health" and entry["status"] == 200
        for entry in captured
    )


def test_dashboard_page_served_in_local_mode(local_mode):
    client = TestClient(app)

    response = client.get("/api/_debug")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_debug_endpoints_are_404_outside_local_mode(monkeypatch):
    monkeypatch.setattr(settings, "CACHE_BACKEND", "valkey")
    client = TestClient(app)

    assert client.get("/api/_debug/requests").status_code == 404
    assert client.get("/api/_debug").status_code == 404
