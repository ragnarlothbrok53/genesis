import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

import pgembed

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = _REPO_ROOT / "data" / "postgres"

_server: Optional["pgembed.PostgresServer"] = None


def _row_exists(server: "pgembed.PostgresServer", query: str) -> bool:
    return "(0 rows)" not in server.psql(query)


def _connection_params(
    server: "pgembed.PostgresServer", user: str, password: str, database: str
) -> dict:
    info = server.get_postmaster_info()
    host = str(info.socket_dir) if info.socket_dir is not None else info.hostname
    return {
        "host": host,
        "port": info.port,
        "database": database,
        "user": user,
        "password": password,
    }


def start() -> dict:
    global _server

    database = os.getenv("POSTGRES_DB", "genesis")
    user = os.getenv("POSTGRES_USER", "genesis")
    password = os.getenv("POSTGRES_PASSWORD", "genesis")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _server = pgembed.get_server(DATA_DIR, cleanup_mode="stop")

    if not _row_exists(_server, f"SELECT 1 FROM pg_roles WHERE rolname = '{user}'"):
        _server.psql(f"CREATE ROLE {user} WITH LOGIN PASSWORD '{password}'")

    if not _row_exists(_server, f"SELECT 1 FROM pg_database WHERE datname = '{database}'"):
        _server.psql(f"CREATE DATABASE {database} OWNER {user}")

    try:
        _server.psql(f"\\c {database}\nCREATE EXTENSION IF NOT EXISTS vector")
    except subprocess.CalledProcessError:
        logger.warning("could not create the pgvector extension — rag module will not work")

    logger.info("pgserver started at %s", DATA_DIR)
    return _connection_params(_server, user, password, database)


def stop() -> None:
    global _server
    if _server is None:
        return
    _server.cleanup()
    _server = None
