import asyncio
import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_TEMPORAL_UI_PORT = 8233


def _start_worker() -> subprocess.Popen | None:
    from genesis.loader import optional_service

    if optional_service("jobs") is None:
        return None
    process = subprocess.Popen([sys.executable, "-m", "genesis.worker"])
    logger.info("Temporal worker started (pid %s)", process.pid)
    return process


def _stop_worker(process: subprocess.Popen | None) -> None:
    if process is None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def serve(dist_dir: Path | None, host: str = "127.0.0.1", port: int = 8000) -> None:
    from genesis.local.temporal import start_local_temporal, stop_local_temporal

    asyncio.run(start_local_temporal(ui_port=_TEMPORAL_UI_PORT))
    os.environ["TEMPORAL_UI_URL"] = f"http://127.0.0.1:{_TEMPORAL_UI_PORT}"

    worker_process = _start_worker()

    from genesis.local.static import mount_spa
    from genesis.main import app

    if dist_dir is not None and mount_spa(app, dist_dir):
        logger.info("serving frontend from %s", dist_dir)
    else:
        logger.info("no frontend build found — running API-only")

    import uvicorn

    try:
        uvicorn.run(app, host=host, port=port, timeout_keep_alive=300)
    finally:
        _stop_worker(worker_process)
        asyncio.run(stop_local_temporal())
