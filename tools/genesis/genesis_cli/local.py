import os
import shutil
import subprocess
from pathlib import Path

from genesis_cli import ux
from genesis_cli.doctor import run_checks

SERVE_SCRIPT = """\
import importlib.util
import os
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("genesis.local.postgres", "genesis/local/postgres.py")
postgres = importlib.util.module_from_spec(spec)
sys.modules["genesis.local.postgres"] = postgres
spec.loader.exec_module(postgres)

params = postgres.start()
os.environ["POSTGRES_HOST"] = str(params["host"])
os.environ["POSTGRES_PORT"] = str(params["port"])

from genesis.local import serve

try:
    serve(Path(sys.argv[1]) if sys.argv[1] else None)
finally:
    postgres.stop()
"""


class LocalError(Exception):
    pass


def _report_checks() -> tuple[bool, bool]:
    checks = run_checks()
    for check in checks:
        if check.present:
            ux.success(f"{check.name} found on PATH")
        elif check.required:
            ux.error(f"{check.name} not found — {check.message}")
        else:
            ux.warning(f"{check.name} not found — {check.message}")
    present = {check.name: check.present for check in checks}
    return present["uv"], present["node"]


def _npm_binary() -> str:
    npm = shutil.which("npm")
    if npm is None:
        raise LocalError("npm not found on PATH even though node is installed")
    return npm


def _ensure_frontend_deps(npm: str, frontend_dir: Path) -> None:
    if (frontend_dir / "node_modules").is_dir():
        return
    print(f"$ npm install (in {frontend_dir})")
    result = subprocess.run([npm, "install"], cwd=frontend_dir, check=False)
    if result.returncode != 0:
        raise LocalError("npm install failed — see output above")


def _build_frontend(npm: str, frontend_dir: Path) -> None:
    print(f"$ npm run build (in {frontend_dir})")
    result = subprocess.run([npm, "run", "build"], cwd=frontend_dir, check=False)
    if result.returncode != 0:
        raise LocalError("npm run build failed — see output above")


def _prepare_frontend(root: Path, node_present: bool) -> Path | None:
    dist_dir = root / "frontend" / "dist"
    if (dist_dir / "index.html").is_file():
        return dist_dir

    if not node_present:
        ux.warning("no frontend/dist and node is unavailable — running API-only")
        return None

    frontend_dir = root / "frontend"
    npm = _npm_binary()
    _ensure_frontend_deps(npm, frontend_dir)
    _build_frontend(npm, frontend_dir)
    if not (dist_dir / "index.html").is_file():
        raise LocalError("npm run build did not produce frontend/dist/index.html")
    return dist_dir


def _serve_command(backend_dir: Path, dist_dir: Path | None) -> list[str]:
    return [
        "uv",
        "run",
        "--project",
        str(backend_dir),
        "--group",
        "local",
        "python",
        "-c",
        SERVE_SCRIPT,
        str(dist_dir) if dist_dir else "",
    ]


def dev_local(root: Path) -> int:
    uv_present, node_present = _report_checks()
    if not uv_present:
        raise LocalError("uv is required for local mode — install it and re-run 'genesis dev --local'")

    dist_dir = _prepare_frontend(root, node_present)

    backend_dir = root / "backend"
    command = _serve_command(backend_dir, dist_dir)
    env = {**os.environ, "CACHE_BACKEND": "embedded", "PYTHONPATH": str(backend_dir)}
    print(f"$ {' '.join(command)}")
    result = subprocess.run(command, cwd=backend_dir, env=env, check=False)
    return result.returncode
