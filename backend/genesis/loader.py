import importlib
import logging
import pkgutil
from collections.abc import Callable

from fastapi import APIRouter, Depends, FastAPI

from genesis.core.config import settings
from genesis.core.database import BaseModel, get_db

logger = logging.getLogger("genesis")


def _iter_modules(package_name: str):
    try:
        package = importlib.import_module(package_name)
    except ModuleNotFoundError:
        return
    for info in sorted(pkgutil.iter_modules(package.__path__), key=lambda m: m.name):
        if not info.name.startswith("_"):
            yield f"{package_name}.{info.name}"


def load_models() -> list[type[BaseModel]]:
    models = []
    for mod_name in _iter_modules("app.models"):
        module = importlib.import_module(mod_name)
        for value in vars(module).values():
            if isinstance(value, type) and issubclass(value, BaseModel) and value is not BaseModel:
                models.append(value)
    return models


def load_tasks() -> list[str]:
    loaded = []
    for mod_name in _iter_modules("app.tasks"):
        importlib.import_module(mod_name)
        loaded.append(mod_name)
    return loaded


def optional_service(name: str):
    try:
        return importlib.import_module(f"genesis.services.{name}")
    except ModuleNotFoundError:
        return None


def load_status_checks() -> dict[str, Callable[[], bool]]:
    checks = {}
    for package in ("genesis.core", "genesis.services"):
        for mod_name in _iter_modules(package):
            module = importlib.import_module(mod_name)
            check = getattr(module, "check", None)
            if callable(check):
                checks[mod_name.rsplit(".", 1)[-1]] = check
    return checks


def load_endpoints(app: FastAPI) -> list[str]:
    prefix = f"/api/{settings.API_VERSION}"
    seen: dict[str, str] = {}
    mounted = []
    dependencies = [Depends(get_db)]
    permissions = optional_service("permissions")
    if permissions is not None:
        dependencies.append(Depends(permissions.enforce))
    for mod_name in _iter_modules("app.endpoints"):
        module = importlib.import_module(mod_name)
        api = getattr(module, "api", None)
        if not isinstance(api, APIRouter):
            logger.warning("genesis: %s defines no 'api = router(...)' — skipped", mod_name)
            continue
        if api.prefix in seen:
            raise RuntimeError(
                f"genesis: route '{api.prefix}' is defined twice "
                f"({seen[api.prefix]} and {mod_name})"
            )
        seen[api.prefix] = mod_name
        app.include_router(api, prefix=prefix, dependencies=dependencies)
        mounted.append(f"{prefix}{api.prefix}")
    return mounted


def autowire(app: FastAPI) -> None:
    models = load_models()
    tasks = load_tasks()
    endpoints = load_endpoints(app)
    app.state.mounted_routes = endpoints
    logger.info(
        "genesis: wired %d models, %d tasks, %d endpoints (%s)",
        len(models),
        len(tasks),
        len(endpoints),
        ", ".join(endpoints) or "none",
    )
