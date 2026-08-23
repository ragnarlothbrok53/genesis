import logging
import time
from contextvars import ContextVar
from pathlib import Path

import peewee
from peewee import Model
from playhouse.pool import PooledPostgresqlDatabase

from genesis.core.config import POSTGRES

logger = logging.getLogger(__name__)

_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"

_db_state_default = {"closed": None, "conn": None, "ctx": None, "transactions": None}
_db_state: ContextVar[dict] = ContextVar("db_state", default=_db_state_default.copy())


class _PeeweeConnectionState(peewee._ConnectionState):
    def __init__(self, **kwargs):
        super().__setattr__("_state", _db_state)
        super().__init__(**kwargs)

    def __setattr__(self, name, value):
        self._state.get()[name] = value

    def __getattr__(self, name):
        return self._state.get()[name]


db = PooledPostgresqlDatabase(
    POSTGRES["database"],
    user=POSTGRES["user"],
    password=POSTGRES["password"],
    host=POSTGRES["host"],
    port=POSTGRES["port"],
    max_connections=16,
    stale_timeout=300,
)
db._state = _PeeweeConnectionState()


class BaseModel(Model):
    class Meta:
        database = db


async def get_db():
    _db_state.set(_db_state_default.copy())
    db._state.reset()
    db.connect(reuse_if_open=True)
    try:
        yield
    finally:
        if not db.is_closed():
            db.close()


def ping() -> bool:
    _db_state.set(_db_state_default.copy())
    db._state.reset()
    try:
        db.connect(reuse_if_open=True)
        db.execute_sql("SELECT 1")
        return True
    except Exception:
        return False
    finally:
        if not db.is_closed():
            db.close()


check = ping


def init_db() -> None:
    from peewee_migrate import Router

    _db_state.set(_db_state_default.copy())
    db._state.reset()
    delay = 0.5
    for attempt in range(1, 11):
        try:
            db.connect(reuse_if_open=True)
            db.execute_sql("SELECT 1")
            break
        except Exception as exc:
            logger.warning("Postgres not ready %d/10 (%s); retrying", attempt, exc)
            time.sleep(delay)
            delay = min(delay * 2, 5.0)
        finally:
            if not db.is_closed():
                db.close()
    else:
        raise RuntimeError("Postgres never became available")

    db.connect(reuse_if_open=True)
    try:
        Router(db, migrate_dir=str(_MIGRATIONS_DIR)).run()
    finally:
        if not db.is_closed():
            db.close()
