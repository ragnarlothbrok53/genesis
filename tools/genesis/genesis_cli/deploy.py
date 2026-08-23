import shutil
import subprocess
import tomllib
from pathlib import Path

FLYCTL_INSTALL_MESSAGE = (
    "flyctl not found on PATH — install it from https://fly.io/docs/flyctl/install/ "
    "(macOS/Linux: curl -L https://fly.io/install.sh | sh ; "
    'Windows: pwsh -c "iwr https://fly.io/install.ps1 -useb | iex"), '
    "then run 'flyctl auth login' and re-run 'genesis deploy'"
)


class DeployError(Exception):
    pass


def check_flyctl() -> bool:
    return shutil.which("flyctl") is not None


def _slugify(name: str) -> str:
    slug = "".join(char if char.isalnum() else "-" for char in name.lower())
    slug = "-".join(part for part in slug.split("-") if part)
    return slug or "genesis-app"


def app_name(root: Path) -> str:
    env_file = root / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("APP_NAME="):
                return _slugify(line.split("=", 1)[1].strip())
    return _slugify(root.name)


def _public_port(root: Path) -> int:
    kernel_path = root / "modules" / "kernel.toml"
    if not kernel_path.is_file():
        return 80
    kernel = tomllib.loads(kernel_path.read_text(encoding="utf-8"))
    for process in kernel.get("process", []):
        if process.get("name") == "nginx":
            return process.get("port", 80)
    return 80


def render_fly_toml(root: Path, name: str) -> str:
    port = _public_port(root)
    return (
        f'app = "{name}"\n'
        'primary_region = "iad"\n'
        "\n"
        "[build]\n"
        "\n"
        "[http_service]\n"
        f"  internal_port = {port}\n"
        "  force_https = true\n"
        "  auto_stop_machines = true\n"
        "  auto_start_machines = true\n"
        "  min_machines_running = 0\n"
        "\n"
        "[[vm]]\n"
        '  memory = "1gb"\n'
        '  cpu_kind = "shared"\n'
        "  cpus = 1\n"
    )


def ensure_fly_toml(root: Path, name: str) -> Path:
    path = root / "fly.toml"
    if not path.is_file():
        path.write_text(render_fly_toml(root, name), encoding="utf-8")
    return path


def deploy(root: Path, dry_run: bool = False, name: str | None = None) -> int:
    resolved_name = name or app_name(root)
    fly_toml = ensure_fly_toml(root, resolved_name)
    command = ["flyctl", "deploy", "--config", str(fly_toml), "--app", resolved_name]

    if dry_run:
        print(f"$ {' '.join(command)}")
        return 0

    if not check_flyctl():
        raise DeployError(FLYCTL_INSTALL_MESSAGE)

    print(f"$ {' '.join(command)}")
    result = subprocess.run(command, cwd=root, check=False)
    return result.returncode
