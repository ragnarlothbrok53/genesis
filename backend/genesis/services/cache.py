import json
import logging
import sqlite3
import threading
import time
from pathlib import Path

import redis

from genesis.core.config import settings

logger = logging.getLogger(__name__)

_client: redis.Redis | None = None
_sqlite: sqlite3.Connection | None = None
_sqlite_lock = threading.Lock()


def _embedded() -> bool:
    return settings.CACHE_BACKEND == "embedded"


def client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(settings.VALKEY_URL, decode_responses=True)
    return _client


def _sqlite_client() -> sqlite3.Connection:
    global _sqlite
    if _sqlite is None:
        path = Path(settings.EMBEDDED_CACHE_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        _sqlite = sqlite3.connect(str(path), check_same_thread=False)
        _sqlite.execute(
            "CREATE TABLE IF NOT EXISTS cache ("
            "key TEXT PRIMARY KEY, value TEXT NOT NULL, expires_at REAL NOT NULL)"
        )
        _sqlite.commit()
    return _sqlite


def check() -> bool:
    try:
        if _embedded():
            _sqlite_client().execute("SELECT 1")
            return True
        return bool(client().ping())
    except Exception:
        return False


def get_json(key: str):
    if not _embedded():
        data = client().get(key)
        return json.loads(data) if data is not None else None
    with _sqlite_lock:
        conn = _sqlite_client()
        row = conn.execute(
            "SELECT value, expires_at FROM cache WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        value, expires_at = row
        if expires_at < time.time():
            conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            conn.commit()
            return None
        return json.loads(value)


def set_json(key: str, value, ttl_seconds: int = 3600) -> None:
    if not _embedded():
        client().set(key, json.dumps(value), ex=ttl_seconds)
        return
    with _sqlite_lock:
        conn = _sqlite_client()
        conn.execute(
            "INSERT INTO cache (key, value, expires_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET "
            "value = excluded.value, expires_at = excluded.expires_at",
            (key, json.dumps(value), time.time() + ttl_seconds),
        )
        conn.commit()


def delete(key: str) -> None:
    if not _embedded():
        client().delete(key)
        return
    with _sqlite_lock:
        conn = _sqlite_client()
        conn.execute("DELETE FROM cache WHERE key = ?", (key,))
        conn.commit()
