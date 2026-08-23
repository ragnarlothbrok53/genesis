import importlib

from genesis import auth, db
from genesis.core.config import settings
from genesis.web import router

_OPTIONAL_MODULES = {
    "ai": "genesis.services.llm",
    "cache": "genesis.services.cache",
    "analytics": "genesis.services.analytics",
    "jobs": "genesis.services.jobs",
    "email": "genesis.services.email",
    "storage": "genesis.services.storage",
    "realtime": "genesis.services.realtime",
}

_OPTIONAL_ATTRS = {
    "task": "jobs",
    "run_task": "jobs",
    "job_status": "jobs",
}


def _load(name: str):
    target = _OPTIONAL_MODULES[name]
    try:
        return importlib.import_module(target)
    except ModuleNotFoundError as exc:
        if exc.name != target:
            raise
        raise AttributeError(
            f"genesis module '{name}' is not installed in this project; "
            f"add it with: genesis add {name}"
        ) from exc


def __getattr__(name: str):
    if name in _OPTIONAL_MODULES:
        return _load(name)
    if name in _OPTIONAL_ATTRS:
        return getattr(_load(_OPTIONAL_ATTRS[name]), name)
    raise AttributeError(f"module 'genesis' has no attribute '{name}'")


__all__ = [
    "db",
    "jobs",
    "ai",
    "cache",
    "auth",
    "analytics",
    "email",
    "storage",
    "realtime",
    "router",
    "task",
    "run_task",
    "job_status",
    "settings",
]
