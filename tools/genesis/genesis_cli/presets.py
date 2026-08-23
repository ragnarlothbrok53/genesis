import secrets
import tomllib
from pathlib import Path

from genesis_cli.modules import ModuleError


def load_presets(modules_dir: Path) -> dict[str, dict]:
    path = modules_dir / "presets.toml"
    if not path.is_file():
        raise ModuleError(f"{path} is missing")
    return tomllib.loads(path.read_text(encoding="utf-8"))


def excluded_for(presets: dict[str, dict], available: set[str], name: str) -> set[str]:
    if name not in presets:
        raise ModuleError(
            f"unknown preset '{name}'; available: {', '.join(sorted(presets))}"
        )
    keep = set(presets[name]["modules"])
    unknown = keep - available
    if unknown:
        raise ModuleError(f"preset '{name}' names unknown module(s): {', '.join(sorted(unknown))}")
    return available - keep


def write_env(root: Path, app_name: str) -> Path:
    example = root / ".env.example"
    target = root / ".env"
    lines = []
    for line in example.read_text(encoding="utf-8").splitlines():
        key = line.split("=", 1)[0].strip() if "=" in line and not line.startswith("#") else None
        if key == "APP_NAME":
            lines.append(f"APP_NAME={app_name}")
        elif key in ("POSTGRES_PASSWORD", "O2_ROOT_PASSWORD", "AUTH_SECRET"):
            lines.append(f"{key}={secrets.token_hex(12)}")
        else:
            lines.append(line)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target
