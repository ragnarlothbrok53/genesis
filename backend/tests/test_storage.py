import pytest

from genesis.core.config import settings
from genesis.services import storage


@pytest.fixture
def local_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "STORAGE_LOCAL_PATH", str(tmp_path))
    yield storage


def test_save_and_get_round_trips(local_storage):
    local_storage.save("widget.txt", b"hello")
    assert local_storage.get("widget.txt") == b"hello"


def test_save_creates_nested_keys(local_storage):
    local_storage.save("uploads/widget.txt", b"hello")
    assert local_storage.get("uploads/widget.txt") == b"hello"


def test_delete_removes_key(local_storage):
    local_storage.save("widget.txt", b"hello")
    local_storage.delete("widget.txt")
    with pytest.raises(FileNotFoundError):
        local_storage.get("widget.txt")


def test_delete_missing_key_is_a_no_op(local_storage):
    local_storage.delete("missing.txt")


def test_get_missing_key_raises_clear_error(local_storage):
    with pytest.raises(FileNotFoundError, match="storage key not found"):
        local_storage.get("missing.txt")


def test_url_returns_file_uri(local_storage):
    local_storage.save("widget.txt", b"hello")
    assert local_storage.url("widget.txt").startswith("file:")


def test_check_reports_healthy(local_storage):
    assert local_storage.check() is True
