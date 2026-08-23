from dataclasses import dataclass

import pytest

from genesis.core.config import settings
from genesis.services import auth


@dataclass
class FakeUser:
    id: int
    email: str
    name: str
    roles: str


@pytest.fixture
def auth_configured(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_SECRET", "test-secret", raising=False)


def request_with_cookie(name: str, value: str):
    from fastapi import Request

    header = f"{name}={value}".encode()
    return Request({"type": "http", "headers": [(b"cookie", header)]})


def test_hash_password_round_trips():
    hashed = auth.hash_password("correct-password")
    assert auth.verify_password("correct-password", hashed)
    assert not auth.verify_password("wrong-password", hashed)


def test_verify_session_returns_none_when_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_SECRET", "", raising=False)
    assert auth.verify_session(request_with_cookie(auth.COOKIE_NAME, "whatever")) is None


def test_verify_session_returns_none_without_cookie(auth_configured):
    from fastapi import Request

    assert auth.verify_session(Request({"type": "http", "headers": []})) is None


def test_create_token_round_trips_through_verify_session(auth_configured):
    user = FakeUser(id=1, email="ada@example.com", name="Ada", roles="admin,user")
    token = auth.create_token(user)

    result = auth.verify_session(request_with_cookie(auth.COOKIE_NAME, token))

    assert result == {
        "id": 1,
        "email": "ada@example.com",
        "name": "Ada",
        "roles": ["admin", "user"],
    }


def test_verify_session_rejects_invalid_token(auth_configured):
    assert auth.verify_session(request_with_cookie(auth.COOKIE_NAME, "not-a-jwt")) is None


def test_check_reflects_configured(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_SECRET", "", raising=False)
    assert auth.check() is False
    monkeypatch.setattr(settings, "AUTH_SECRET", "test-secret", raising=False)
    assert auth.check() is True
