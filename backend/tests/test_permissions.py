import peewee
import pytest
from fastapi import HTTPException, Request

from app.models.permission import PermissionRule
from genesis.services import permissions


def request_for(method: str, path: str) -> Request:
    return Request({"type": "http", "method": method, "path": path, "headers": []})


@pytest.fixture(autouse=True)
def sqlite_permission_rules():
    sqlite = peewee.SqliteDatabase(":memory:")
    PermissionRule.bind(sqlite, bind_refs=False, bind_backrefs=False)
    sqlite.create_tables([PermissionRule])
    yield
    sqlite.drop_tables([PermissionRule])
    sqlite.close()


def test_no_rules_allows_everyone(monkeypatch):
    monkeypatch.setattr(permissions, "current_user", lambda request: None)
    permissions.enforce(request_for("GET", "/api/v1/items"))


def test_matching_role_is_allowed(monkeypatch):
    PermissionRule.create(method="*", path="/api/v1/items", role="staff")
    monkeypatch.setattr(
        permissions, "current_user", lambda request: {"email": "a@x.com", "roles": ["staff"]}
    )
    permissions.enforce(request_for("GET", "/api/v1/items"))


def test_non_matching_role_is_forbidden(monkeypatch):
    PermissionRule.create(method="*", path="/api/v1/items", role="staff")
    monkeypatch.setattr(
        permissions, "current_user", lambda request: {"email": "a@x.com", "roles": ["viewer"]}
    )
    with pytest.raises(HTTPException) as raised:
        permissions.enforce(request_for("GET", "/api/v1/items"))
    assert raised.value.status_code == 403


def test_anonymous_is_forbidden_when_rule_exists(monkeypatch):
    PermissionRule.create(method="*", path="/api/v1/items", role="staff")
    monkeypatch.setattr(permissions, "current_user", lambda request: None)
    with pytest.raises(HTTPException):
        permissions.enforce(request_for("GET", "/api/v1/items"))


def test_method_specific_rule_only_restricts_that_method(monkeypatch):
    PermissionRule.create(method="DELETE", path="/api/v1/items", role="admin")
    monkeypatch.setattr(
        permissions, "current_user", lambda request: {"email": "a@x.com", "roles": []}
    )
    permissions.enforce(request_for("GET", "/api/v1/items"))
    with pytest.raises(HTTPException):
        permissions.enforce(request_for("DELETE", "/api/v1/items"))


def test_unrelated_path_is_unaffected(monkeypatch):
    PermissionRule.create(method="*", path="/api/v1/items", role="staff")
    monkeypatch.setattr(
        permissions, "current_user", lambda request: {"email": "a@x.com", "roles": []}
    )
    permissions.enforce(request_for("GET", "/api/v1/jobs"))
