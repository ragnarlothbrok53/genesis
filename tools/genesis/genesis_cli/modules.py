import tomllib
from pathlib import Path

KERNEL_CAPABILITIES = {"database", "observability", "web"}


class ModuleError(Exception):
    pass


def load_kernel(modules_dir: Path) -> dict:
    return tomllib.loads((modules_dir / "kernel.toml").read_text(encoding="utf-8"))


def load_modules(modules_dir: Path) -> dict[str, dict]:
    modules = {}
    for manifest_path in sorted(modules_dir.glob("*/module.toml")):
        manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
        name = manifest["name"]
        if name != manifest_path.parent.name:
            raise ModuleError(
                f"{manifest_path}: name '{name}' does not match directory "
                f"'{manifest_path.parent.name}'"
            )
        modules[name] = manifest
    return modules


def resolve(modules: dict[str, dict], excluded: set[str]) -> set[str]:
    unknown = excluded - modules.keys()
    if unknown:
        raise ModuleError(
            f"unknown module(s): {', '.join(sorted(unknown))}; "
            f"available: {', '.join(sorted(modules))}"
        )

    selected = set(modules) - excluded
    for name in sorted(selected):
        for dependency in modules[name].get("requires", []):
            if dependency in KERNEL_CAPABILITIES:
                continue
            if dependency in excluded:
                raise ModuleError(f"module '{name}' requires '{dependency}', which was excluded")
            if dependency not in modules:
                raise ModuleError(f"module '{name}' requires unknown module '{dependency}'")
    return selected
