import pytest
from fastapi import Request

from genesis import auth
from genesis.core.config import settings


def request_with(headers: dict, cookies: dict | None = None) -> Request:
    header_list = [(key.lower().encode(), value.encode()) for key, value in headers.items()]
    if cookies:
        cookie_header = "; ".join(f"{key}={value}" for key, value in cookies.items())
        header_list.append((b"cookie", cookie_header.encode()))
    return Request({"type": "http", "headers": header_list})


@pytest.fixture
def auth_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_SECRET", "", raising=False)


@pytest.fixture
def auth_configured(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_SECRET", "test-secret", raising=False)


def test_falls_back_to_header_passthrough_when_unconfigured(auth_unconfigured):
    user = auth.current_user(
        request_with({"x-auth-request-email": "ada@example.com", "x-auth-request-roles": "admin"})
    )
    assert user == {"email": "ada@example.com", "name": "ada@example.com", "roles": ["admin"]}


def test_uses_session_cookie_when_configured(monkeypatch, auth_configured):
    from genesis.services import auth as auth_service

    monkeypatch.setattr(
        auth_service,
        "verify_session",
        lambda request: {"email": "grace@example.com", "name": "Grace", "roles": ["admin"]},
    )

    user = auth.current_user(request_with({}))
    assert user == {"email": "grace@example.com", "name": "Grace", "roles": ["admin"]}


def test_falls_back_to_headers_when_no_session_cookie(monkeypatch, auth_configured):
    from genesis.services import auth as auth_service

    monkeypatch.setattr(auth_service, "verify_session", lambda request: None)

    user = auth.current_user(request_with({"x-auth-request-email": "ada@example.com"}))
    assert user["email"] == "ada@example.com"


def test_require_admin_still_works_through_facade(monkeypatch, auth_unconfigured):
    from fastapi import HTTPException

    from genesis.core import identity

    monkeypatch.setattr(identity, "_DEV_BYPASS", False)

    with pytest.raises(HTTPException) as raised:
        auth.require_admin(request_with({}))
    assert raised.value.status_code == 401
