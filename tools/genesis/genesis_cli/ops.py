import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

HEALTH_URL = "http://localhost:8000/api/health"

MIGRATE_SCRIPT = (
    "cd /app/backend && uv run --no-sync python -c "
    '"from genesis.loader import load_models; '
    "from genesis.core.database import db; "
    "from peewee_migrate import Router; "
    "models = load_models(); "
    "print(f'discovered {len(models)} model(s)'); "
    "router = Router(db, migrate_dir='migrations'); "
    "router.create('{message}', auto=models); "
    'router.run()"'
)


class OpsError(Exception):
    pass


def _require_docker() -> None:
    if shutil.which("docker") is None:
        raise OpsError("docker not found on PATH — install Docker, Rancher Desktop or OrbStack")
    result = subprocess.run(
        ["docker", "info"], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise OpsError("docker is installed but not running — start it and try again")


def _compose(root, *arguments: str, stream: bool = True) -> int:
    command = ["docker", "compose", "--profile", "dev", *arguments]
    print(f"$ {' '.join(command)}")
    completed = subprocess.run(
        command, cwd=root, check=False, capture_output=not stream, text=True
    )
    if not stream and completed.returncode != 0:
        print(completed.stdout or "", file=sys.stderr)
        print(completed.stderr or "", file=sys.stderr)
    return completed.returncode


def _wait_for_health(timeout: float = 180.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=3) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(3)
    return False


def dev(root, build: bool = True) -> int:
    _require_docker()
    arguments = ["up", "-d", "--build"] if build else ["up", "-d"]
    code = _compose(root, *arguments)
    if code != 0:
        return code
    print("waiting for the app to become healthy…")
    if not _wait_for_health():
        print("error: app did not become healthy — run 'genesis logs'", file=sys.stderr)
        return 1
    print("ready at http://localhost:8000")
    return 0


def build(root) -> int:
    _require_docker()
    return _compose(root, "build")


def down(root) -> int:
    _require_docker()
    return _compose(root, "--profile", "prod", "down")


def logs(root) -> int:
    _require_docker()
    return _compose(root, "logs", "-f")


def restart(root, process: str) -> int:
    _require_docker()
    return _compose(root, "exec", "-T", "app_dev", "supervisorctl", "restart", process)


def migrate(root, message: str) -> int:
    _require_docker()
    if '"' in message or "'" in message:
        raise OpsError("migration message cannot contain quotes")
    print(f"generating and applying a migration: {message}")
    return _compose(
        root,
        "exec",
        "-T",
        "-e",
        "PYTHONPATH=/app/backend",
        "app_dev",
        "sh",
        "-c",
        MIGRATE_SCRIPT.replace("{message}", message),
    )
