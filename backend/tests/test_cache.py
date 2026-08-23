import time

import pytest

from genesis.core.config import settings
from genesis.services import cache


@pytest.fixture
def embedded_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CACHE_BACKEND", "embedded")
    monkeypatch.setattr(settings, "EMBEDDED_CACHE_PATH", str(tmp_path / "cache.db"))
    monkeypatch.setattr(cache, "_sqlite", None)
    yield cache
    monkeypatch.setattr(cache, "_sqlite", None)


def test_missing_key_returns_none(embedded_cache):
    assert embedded_cache.get_json("missing") is None


def test_json_round_trips(embedded_cache):
    embedded_cache.set_json("widget", {"name": "gizmo", "count": 3})
    assert embedded_cache.get_json("widget") == {"name": "gizmo", "count": 3}


def test_set_json_overwrites_existing_key(embedded_cache):
    embedded_cache.set_json("widget", {"count": 1})
    embedded_cache.set_json("widget", {"count": 2})
    assert embedded_cache.get_json("widget") == {"count": 2}


def test_expired_key_returns_none(embedded_cache, monkeypatch):
    embedded_cache.set_json("widget", {"count": 1}, ttl_seconds=1)
    later = time.time() + 2
    monkeypatch.setattr(time, "time", lambda: later)
    assert embedded_cache.get_json("widget") is None


def test_delete_removes_key(embedded_cache):
    embedded_cache.set_json("widget", {"count": 1})
    embedded_cache.delete("widget")
    assert embedded_cache.get_json("widget") is None


def test_delete_missing_key_is_a_no_op(embedded_cache):
    embedded_cache.delete("missing")


def test_check_reports_healthy(embedded_cache):
    assert embedded_cache.check() is True
