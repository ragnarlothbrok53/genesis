import os

import httpx
import pytest

BASE_URL = os.getenv("GENESIS_URL", "http://localhost:8000")


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=BASE_URL, timeout=15.0) as http:
        try:
            http.get("/api/health")
        except httpx.HTTPError:
            pytest.skip(f"no app running at {BASE_URL}")
        yield http


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_status_reports_named_services(client):
    services = client.get("/api/status").json()["services"]
    names = {service["name"] for service in services}
    assert {"database", "dbgate", "observability"} <= names
    assert all(isinstance(service["up"], bool) for service in services)


def test_me_returns_a_user(client):
    body = client.get("/api/me").json()
    assert "email" in body and "roles" in body


def test_item_lifecycle(client):
    created = client.post("/api/v1/items", json={"name": "test-item", "description": "x"})
    assert created.status_code == 201
    item = created.json()
    assert item["name"] == "test-item"
    assert set(item) == {"id", "name", "description", "created_at"}

    listed = client.get("/api/v1/items").json()
    assert any(row["id"] == item["id"] for row in listed)

    assert client.delete(f"/api/v1/items/{item['id']}").status_code == 204
    assert client.delete(f"/api/v1/items/{item['id']}").status_code == 404


def test_item_rejects_blank_name(client):
    assert client.post("/api/v1/items", json={"name": ""}).status_code == 422


def test_unknown_job_is_404(client):
    assert client.get("/api/v1/jobs/job-does-not-exist").status_code == 404


def test_job_rejects_out_of_range_seconds(client):
    assert client.post("/api/v1/jobs", json={"seconds": 999}).status_code == 422


def test_openapi_covers_every_response(client):
    schema = client.get("/api/openapi.json").json()
    untyped = []
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            ok = operation.get("responses", {}).get("200") or operation.get("responses", {}).get(
                "201"
            )
            if ok and "content" not in ok and ok.get("description") != "No Content":
                untyped.append(f"{method.upper()} {path}")
    assert not untyped, f"endpoints missing a response schema: {untyped}"
