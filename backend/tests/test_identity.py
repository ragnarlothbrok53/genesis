import pytest
from fastapi import HTTPException

from genesis.core import identity


def request_with(headers: dict):
    scope = {
        "type": "http",
        "headers": [(key.lower().encode(), value.encode()) for key, value in headers.items()],
    }
    from fastapi import Request

    return Request(scope)


def test_proxy_headers_become_the_user():
    user = identity.current_user(
        request_with(
            {
                "x-auth-request-email": "ada@example.com",
                "x-auth-request-user": "Ada",
                "x-auth-request-roles": "admin, viewer",
            }
        )
    )
    assert user == {"email": "ada@example.com", "name": "Ada", "roles": ["admin", "viewer"]}


def test_name_falls_back_to_email():
    user = identity.current_user(request_with({"x-auth-request-email": "ada@example.com"}))
    assert user["name"] == "ada@example.com"


def test_blank_roles_header_yields_no_roles():
    user = identity.current_user(
        request_with({"x-auth-request-email": "ada@example.com", "x-auth-request-roles": " , "})
    )
    assert user["roles"] == []


def test_no_headers_uses_dev_user_in_development(monkeypatch):
    monkeypatch.setattr(identity, "_DEV_BYPASS", True)
    assert identity.current_user(request_with({}))["roles"] == ["admin"]


def test_no_headers_is_anonymous_outside_development(monkeypatch):
    monkeypatch.setattr(identity, "_DEV_BYPASS", False)
    assert identity.current_user(request_with({})) is None


def test_require_admin_rejects_anonymous(monkeypatch):
    monkeypatch.setattr(identity, "_DEV_BYPASS", False)
    with pytest.raises(HTTPException) as raised:
        identity.require_admin(request_with({}))
    assert raised.value.status_code == 401


def test_require_admin_rejects_non_admin():
    with pytest.raises(HTTPException) as raised:
        identity.require_admin(
            request_with(
                {"x-auth-request-email": "ada@example.com", "x-auth-request-roles": "viewer"}
            )
        )
    assert raised.value.status_code == 403


def test_require_admin_allows_admin():
    user = identity.require_admin(
        request_with({"x-auth-request-email": "ada@example.com", "x-auth-request-roles": "admin"})
    )
    assert user["email"] == "ada@example.com"
