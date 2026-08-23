import json
import shutil
import subprocess
from pathlib import Path

from genesis_cli.modules import ModuleError, load_kernel, load_modules
from genesis_cli.paths import SKIP_DIRS, iter_text_files
from genesis_cli.scan import installed_modules
from genesis_cli.strip import MarkerError, declared_markers, strip_excluded


class SyncError(Exception):
    pass


def _target_root(path: Path) -> Path:
    if not (path / "modules" / "kernel.toml").is_file():
        raise SyncError(f"{path} is not a genesis project (no modules/kernel.toml)")
    return path


def _all_capability_markers(modules: dict[str, dict], kernel: dict) -> set[str]:
    known = {f"module:{name}" for name in modules}
    services = list(kernel.get("service", []))
    for manifest in modules.values():
        services += manifest.get("service", [])
    known |= {f"service:{service['name']}" for service in services}
    known |= {"topology:single", "topology:compose"}
    return known


def _dependents_of(modules: dict[str, dict], installed: set[str], name: str) -> list[str]:
    return sorted(
        other
        for other in installed
        if other != name and name in modules.get(other, {}).get("requires", [])
    )


def _requires_closure(modules: dict[str, dict], installed: set[str], name: str) -> set[str]:
    if name not in modules:
        raise SyncError(f"unknown module '{name}'; available: {', '.join(sorted(modules))}")
    needed = {name}
    frontier = [name]
    while frontier:
        current = frontier.pop()
        for dependency in modules[current].get("requires", []):
            if dependency in installed or dependency in needed:
                continue
            if dependency not in modules:
                continue  # kernel capability (e.g. "database"), not a module to add
            needed.add(dependency)
            frontier.append(dependency)
    return needed


def _copy_owned_files(source: Path, target: Path, modules: dict[str, dict], name: str) -> list[str]:
    copied = []
    for entry in modules[name].get("files", []):
        clean = entry.rstrip("/")
        source_path = source / clean
        target_path = target / clean
        if not source_path.exists():
            continue
        if target_path.exists():
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if source_path.is_dir():
            shutil.copytree(source_path, target_path)
        else:
            shutil.copy2(source_path, target_path)
        copied.append(entry)
    return copied


def _resync_infra(source: Path, target: Path, known: set[str], old: set[str], new: set[str]) -> tuple[list[str], list[str]]:
    updated, skipped = [], []
    for source_path in iter_text_files(source):
        relative = source_path.relative_to(source)
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        full = source_path.read_text(encoding="utf-8")
        if not any(kind in full for kind in ("module:", "service:", "topology:")):
            continue

        unknown = declared_markers(full) - known
        if unknown:
            raise MarkerError(f"{source_path}: unknown marker(s): {', '.join(sorted(unknown))}")

        expected_before = strip_excluded(full, old, source=str(source_path))
        target_path = target / relative
        if not target_path.exists():
            continue
        current = target_path.read_text(encoding="utf-8")
        if current != expected_before:
            skipped.append(str(relative).replace("\\", "/"))
            continue

        expected_after = strip_excluded(full, new, source=str(source_path))
        if expected_after != current:
            target_path.write_text(expected_after, encoding="utf-8")
            updated.append(str(relative).replace("\\", "/"))
    return updated, skipped


def _env_delta(source: Path, added: set[str], old_excluded: set[str], new_excluded: set[str]) -> list[str]:
    example = source / ".env.example"
    if not example.is_file():
        return []
    full = example.read_text(encoding="utf-8")
    before = strip_excluded(full, old_excluded)
    after = strip_excluded(full, new_excluded)
    before_lines = set(before.splitlines())
    new_lines = [line for line in after.splitlines() if line not in before_lines and "=" in line]
    return new_lines


def _append_env(target: Path, new_lines: list[str]) -> list[str]:
    env_path = target / ".env"
    if not env_path.is_file() or not new_lines:
        return []
    existing = env_path.read_text(encoding="utf-8")
    existing_keys = {
        line.split("=", 1)[0] for line in existing.splitlines() if "=" in line and not line.startswith("#")
    }
    to_append = [
        line for line in new_lines if line.split("=", 1)[0] not in existing_keys and not line.startswith("#")
    ]
    if to_append:
        with env_path.open("a", encoding="utf-8") as handle:
            handle.write("\n" + "\n".join(to_append) + "\n")
    return to_append


def _relock(target: Path) -> bool:
    backend = target / "backend"
    if not (backend / "pyproject.toml").is_file():
        return True
    lock = backend / "uv.lock"
    if lock.exists():
        lock.unlink()
    try:
        subprocess.run(["uv", "lock", "--directory", str(backend)], check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


def _split_npm_spec(spec: str) -> tuple[str, str]:
    if "@" in spec[1:]:
        index = spec.rindex("@")
        return spec[:index], spec[index + 1 :]
    return spec, "latest"


def _add_npm_deps(target: Path, deps: list[str]) -> list[str]:
    package_json = target / "frontend" / "package.json"
    if not deps or not package_json.is_file():
        return []
    data = json.loads(package_json.read_text(encoding="utf-8"))
    dependencies = data.setdefault("dependencies", {})
    added = []
    for spec in deps:
        name, version = _split_npm_spec(spec)
        if name in dependencies:
            continue
        dependencies[name] = version
        added.append(name)
    if added:
        package_json.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return added


def _remove_npm_deps(target: Path, deps: list[str]) -> list[str]:
    package_json = target / "frontend" / "package.json"
    if not deps or not package_json.is_file():
        return []
    data = json.loads(package_json.read_text(encoding="utf-8"))
    dependencies = data.get("dependencies", {})
    removed = []
    for spec in deps:
        name, _version = _split_npm_spec(spec)
        if name in dependencies:
            del dependencies[name]
            removed.append(name)
    if removed:
        package_json.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return removed


def _npm_relock(target: Path, deps: list[str]) -> bool:
    if not deps:
        return True
    frontend = target / "frontend"
    if not (frontend / "package.json").is_file():
        return True
    try:
        subprocess.run(
            ["npm", "install", "--package-lock-only"],
            cwd=frontend,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


def add(target: Path, source: Path, name: str, relock: bool = True) -> dict:
    target = _target_root(target)
    modules = load_modules(source / "modules")
    kernel = load_kernel(source / "modules")
    installed = set(installed_modules(target, modules))

    if name in installed:
        raise SyncError(f"module '{name}' is already installed")

    to_add = _requires_closure(modules, installed, name)
    known = _all_capability_markers(modules, kernel)
    old_excluded = {f"module:{n}" for n in modules if n not in installed}
    new_excluded = {f"module:{n}" for n in modules if n not in installed | to_add}

    copied: list[str] = []
    npm_deps: list[str] = []
    for module_name in sorted(to_add):
        copied += _copy_owned_files(source, target, modules, module_name)
        npm_deps += modules[module_name].get("npm_deps", [])

    updated, skipped = _resync_infra(source, target, known, old_excluded, new_excluded)
    env_lines = _env_delta(source, to_add, old_excluded, new_excluded)
    appended_env = _append_env(target, env_lines)
    relocked = _relock(target) if relock else True
    npm_added = _add_npm_deps(target, npm_deps)
    npm_relocked = _npm_relock(target, npm_deps) if relock else True

    return {
        "added": sorted(to_add),
        "copied": copied,
        "infra_updated": updated,
        "infra_skipped": skipped,
        "env_appended": appended_env,
        "relocked": relocked,
        "npm_added": npm_added,
        "npm_relocked": npm_relocked,
    }


def remove(target: Path, source: Path, name: str, relock: bool = True) -> dict:
    target = _target_root(target)
    modules = load_modules(source / "modules")
    kernel = load_kernel(source / "modules")
    installed = set(installed_modules(target, modules))

    if name not in modules:
        raise ModuleError(f"unknown module '{name}'; available: {', '.join(sorted(modules))}")
    if name not in installed:
        raise SyncError(f"module '{name}' is not installed")

    dependents = _dependents_of(modules, installed, name)
    if dependents:
        raise SyncError(f"module '{name}' is required by: {', '.join(dependents)}")

    known = _all_capability_markers(modules, kernel)
    old_excluded = {f"module:{n}" for n in modules if n not in installed}
    new_excluded = old_excluded | {f"module:{name}"}

    removed = []
    for entry in modules[name].get("files", []):
        path = target / entry.rstrip("/")
        if not path.exists():
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        removed.append(entry)

    updated, skipped = _resync_infra(source, target, known, old_excluded, new_excluded)
    relocked = _relock(target) if relock else True
    npm_deps = modules[name].get("npm_deps", [])
    npm_removed = _remove_npm_deps(target, npm_deps)
    npm_relocked = _npm_relock(target, npm_deps) if relock else True

    return {
        "removed_files": removed,
        "infra_updated": updated,
        "infra_skipped": skipped,
        "relocked": relocked,
        "npm_removed": npm_removed,
        "npm_relocked": npm_relocked,
    }
