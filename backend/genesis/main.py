import logging
import os
import threading
from contextlib import asynccontextmanager

import peewee
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

from genesis.auth import current_user
from genesis.core.config import settings
from genesis.core.database import init_db
from genesis.core.debug_dashboard import setup_debug_dashboard
from genesis.core.observability import setup_observability
from genesis.loader import autowire, load_status_checks, optional_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    llm = optional_service("llm")
    if llm and llm.check():
        threading.Thread(target=llm.warm, daemon=True).start()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.API_VERSION,
    docs_url=None,
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

setup_observability(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials="*" not in settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

setup_debug_dashboard(app)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_request: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(peewee.ProgrammingError)
async def db_schema_error_handler(_request: Request, exc: peewee.ProgrammingError):
    detail = f"Database error: {exc}"
    if "does not exist" in str(exc):
        detail += ' — your schema may be out of date; run: manage migrate "describe change"'
    return JSONResponse(status_code=500, content={"detail": detail})


class Health(BaseModel):
    status: str
    app: str


class ServiceStatus(BaseModel):
    name: str
    up: bool
    url: str | None = None


class Status(BaseModel):
    services: list[ServiceStatus]


class CurrentUser(BaseModel):
    id: int | None = None
    email: str
    name: str
    roles: list[str]


@app.get("/api/health", response_model=Health)
async def health():
    return {"status": "ok", "app": settings.APP_NAME}


def _service_url(name: str) -> str | None:
    if name == "dbgate":
        return "/db"
    if name == "jobs":
        return os.environ.get("TEMPORAL_UI_URL", "/temporal/")
    if name == "observability":
        return "/o11y/web"
    return None


@app.get("/api/status", response_model=Status)
def status():
    return {
        "services": [
            {"name": name, "up": check(), "url": _service_url(name)}
            for name, check in load_status_checks().items()
        ]
    }


@app.get("/api/me", response_model=CurrentUser)
async def me(request: Request):
    user = current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"detail": "Unauthenticated"})
    return user


autowire(app)
