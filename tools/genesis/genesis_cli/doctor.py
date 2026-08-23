import shutil
import subprocess
import sys
from dataclasses import dataclass

UV_INSTALL_URL_UNIX = "https://astral.sh/uv/install.sh"
UV_INSTALL_URL_WINDOWS = "https://astral.sh/uv/install.ps1"


@dataclass
class Check:
    name: str
    present: bool
    required: bool
    message: str


def check_uv() -> Check:
    present = shutil.which("uv") is not None
    message = (
        "uv is genesis's only real prerequisite — install it with the official script: "
        f"{UV_INSTALL_URL_UNIX} (macOS/Linux) or {UV_INSTALL_URL_WINDOWS} (Windows)"
    )
    return Check("uv", present, required=True, message=message)


def check_node() -> Check:
    present = shutil.which("node") is not None
    message = "optional, needed only for frontend dev with hot reload — install from https://nodejs.org"
    return Check("node", present, required=False, message=message)


def check_npm() -> Check:
    present = shutil.which("npm") is not None
    message = (
        "optional, needed only for building the frontend in local mode — usually bundled with "
        "node, but some node installs strip it — install from https://nodejs.org"
    )
    return Check("npm", present, required=False, message=message)


def check_docker() -> Check:
    present = shutil.which("docker") is not None
    message = (
        "optional if you always use 'genesis dev --local' — required for the default "
        "Docker-based workflow (dev/build/down/logs/restart/migrate) — install Docker, "
        "Rancher Desktop or OrbStack"
    )
    return Check("docker", present, required=False, message=message)


def check_flyctl() -> Check:
    present = shutil.which("flyctl") is not None
    message = "optional, needed only for 'genesis deploy' (Fly.io) — install from https://fly.io/docs/flyctl/install/"
    return Check("flyctl", present, required=False, message=message)


def run_checks() -> list[Check]:
    return [check_uv(), check_node(), check_npm(), check_docker(), check_flyctl()]


def install_uv() -> int:
    if sys.platform == "win32":
        command = [
            "powershell",
            "-ExecutionPolicy",
            "ByPass",
            "-c",
            f"irm {UV_INSTALL_URL_WINDOWS} | iex",
        ]
    else:
        command = ["sh", "-c", f"curl -LsSf {UV_INSTALL_URL_UNIX} | sh"]
    return subprocess.run(command, check=False).returncode
