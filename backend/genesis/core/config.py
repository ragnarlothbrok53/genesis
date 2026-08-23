import os
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv
from dynaconf import Dynaconf

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

# Resolve config files by absolute path relative to the backend root so settings
# load regardless of the process working directory (the unified container runs
# with CWD != this file's location).
_BACKEND_DIR = Path(__file__).resolve().parents[2]  # core -> genesis -> backend
_REPO_ROOT = _BACKEND_DIR.parent
_SETTINGS_FILE = _BACKEND_DIR / "settings.toml"
_ENV_FILE = _REPO_ROOT / ".env"  # unified env at repo root

if os.getenv("ENV_FOR_DYNACONF", "development") == "development":
    load_dotenv(_ENV_FILE)

settings = Dynaconf(
    settings_files=[str(_SETTINGS_FILE), str(_ENV_FILE)],
    environments=True,
    envvar_prefix=False,
)

def _address(service: str, default_port: int) -> tuple[str, int]:
    return (
        os.getenv(f"{service}_HOST", "127.0.0.1"),
        int(os.getenv(f"{service}_PORT", str(default_port))),
    )


_pg_host, _pg_port = _address("POSTGRES", 5432)
POSTGRES = {
    "host": _pg_host,
    "port": _pg_port,
    "database": os.getenv("POSTGRES_DB", "genesis"),
    "user": os.getenv("POSTGRES_USER", "genesis"),
    "password": os.getenv("POSTGRES_PASSWORD", "genesis"),
}

_valkey_host, _valkey_port = _address("VALKEY", 6379)
DBGATE = dict(zip(("host", "port"), _address("DBGATE", 3000)))
_temporal_host, _temporal_port = _address("TEMPORAL", 7233) # module:jobs
_openobserve_host, _openobserve_port = _address("OPENOBSERVE", 5080)

settings.set("POSTGRES", POSTGRES)
settings.set(
    "DATABASE_URL",
    f"postgresql://{quote(POSTGRES['user'], safe='')}:{quote(POSTGRES['password'], safe='')}"
    f"@{POSTGRES['host']}:{POSTGRES['port']}/{POSTGRES['database']}",
)
settings.set("VALKEY_URL", os.getenv("VALKEY_URL") or f"redis://{_valkey_host}:{_valkey_port}/0")
_IN_DOCKER = Path("/.dockerenv").exists()
_DEFAULT_CACHE_BACKEND = "valkey" if _IN_DOCKER else "embedded"
settings.set("CACHE_BACKEND", os.getenv("CACHE_BACKEND") or _DEFAULT_CACHE_BACKEND)
settings.set(
    "EMBEDDED_CACHE_PATH",
    os.getenv("EMBEDDED_CACHE_PATH") or str(_REPO_ROOT / "data" / "cache.db"),
)
settings.set("TEMPORAL_ADDRESS", f"{_temporal_host}:{_temporal_port}") # module:jobs
_otel_org = settings.get("OTEL_ORG", "default")
settings.set(
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    or f"http://{_openobserve_host}:{_openobserve_port}/o11y/api/{_otel_org}",
)