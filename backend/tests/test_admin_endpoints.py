import peewee
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.endpoints.admin_permissions import api as permissions_api
from app.endpoints.admin_users import api as users_api
from app.models.permission import PermissionRule
from app.models.user import User
from genesis.auth import require_admin

ADMIN = {"email": "admin@example.com", "name": "Admin", "roles": ["admin"]}


@pytest.fixture
def users_client(tmp_path):
    sqlite = peewee.SqliteDatabase(str(tmp_path / "users.sqlite3"))
    User.bind(sqlite, bind_refs=False, bind_backrefs=False)
    sqlite.create_tables([User])

    app = FastAPI()
    app.include_router(users_api, prefix="/api/v1")
    app.dependency_overrides[require_admin] = lambda: ADMIN

    User.create(email=ADMIN["email"], name="Admin", password_hash="x", roles="admin")
    User.create(email="viewer@example.com", name="Viewer", password_hash="x", roles="")

    yield TestClient(app)

    sqlite.drop_tables([User])
    sqlite.close()


@pytest.fixture
def permissions_client(tmp_path):
    sqlite = peewee.SqliteDatabase(str(tmp_path / "permissions.sqlite3"))
    PermissionRule.bind(sqlite, bind_refs=False, bind_backrefs=False)
    sqlite.create_tables([PermissionRule])

    app = FastAPI()
    app.include_router(permissions_api, prefix="/api/v1")
    app.state.mounted_routes = ["/api/v1/items", "/api/v1/jobs"]
    app.dependency_overrides[require_admin] = lambda: ADMIN

    yield TestClient(app)

    sqlite.drop_tables([PermissionRule])
    sqlite.close()


def test_list_users(users_client):
    body = users_client.get("/api/v1/admin/users").json()
    assert {row["email"] for row in body} == {ADMIN["email"], "viewer@example.com"}


def test_update_roles(users_client):
    viewer = User.get(User.email == "viewer@example.com")
    response = users_client.patch(f"/api/v1/admin/users/{viewer.id}", json={"roles": ["staff"]})
    assert response.status_code == 200
    assert response.json()["roles"] == ["staff"]


def test_cannot_deactivate_yourself(users_client):
    admin = User.get(User.email == ADMIN["email"])
    response = users_client.post(f"/api/v1/admin/users/{admin.id}/deactivate")
    assert response.status_code == 400


def test_deactivate_other_user(users_client):
    viewer = User.get(User.email == "viewer@example.com")
    response = users_client.post(f"/api/v1/admin/users/{viewer.id}/deactivate")
    assert response.status_code == 200
    assert response.json()["active"] is False


def test_cannot_delete_yourself(users_client):
    admin = User.get(User.email == ADMIN["email"])
    response = users_client.delete(f"/api/v1/admin/users/{admin.id}")
    assert response.status_code == 400


def test_delete_other_user(users_client):
    viewer = User.get(User.email == "viewer@example.com")
    response = users_client.delete(f"/api/v1/admin/users/{viewer.id}")
    assert response.status_code == 204
    assert User.get_or_none(User.email == "viewer@example.com") is None


def test_permission_rule_lifecycle(permissions_client):
    created = permissions_client.post(
        "/api/v1/admin/permissions", json={"method": "*", "path": "/api/v1/items", "role": "staff"}
    )
    assert created.status_code == 201
    rule_id = created.json()["id"]

    listed = permissions_client.get("/api/v1/admin/permissions").json()
    assert any(rule["id"] == rule_id for rule in listed)

    assert permissions_client.delete(f"/api/v1/admin/permissions/{rule_id}").status_code == 204
    assert permissions_client.delete(f"/api/v1/admin/permissions/{rule_id}").status_code == 404


def test_list_routes(permissions_client):
    body = permissions_client.get("/api/v1/admin/permissions/routes").json()
    assert body == ["/api/v1/items", "/api/v1/jobs"]
