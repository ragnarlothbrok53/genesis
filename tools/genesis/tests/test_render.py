import argparse
import hashlib
from pathlib import Path

import pytest

from genesis_cli.cli import find_template, render
from genesis_cli.modules import ModuleError, load_modules, resolve

TEMPLATE = Path(__file__).resolve().parents[3]


def render_to(tmp_path: Path, name: str, **overrides) -> Path:
    out = tmp_path / name
    args = argparse.Namespace(
        out=str(out),
        without=[],
        topology="single",
        force=True,
        source=str(TEMPLATE),
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    assert render(args) == 0
    return out


def digest(root: Path) -> dict[str, str]:
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "uv.lock":
            key = str(path.relative_to(root)).replace("\\", "/")
            files[key] = hashlib.md5(path.read_bytes()).hexdigest()
    return files


def test_template_is_discoverable():
    assert (find_template(str(TEMPLATE)) / "modules" / "kernel.toml").is_file()


def test_rejects_directory_without_kernel(tmp_path):
    with pytest.raises(ModuleError, match="not a genesis template"):
        find_template(str(tmp_path))


def test_unknown_module_rejected():
    modules = load_modules(TEMPLATE / "modules")
    with pytest.raises(ModuleError, match="unknown module"):
        resolve(modules, {"nope"})


def test_excluding_a_dependency_is_rejected():
    modules = load_modules(TEMPLATE / "modules")
    modules["demo"] = {"name": "demo", "requires": ["cache"]}
    with pytest.raises(ModuleError, match="requires 'cache'"):
        resolve(modules, {"cache"})


def test_render_is_deterministic(tmp_path):
    first = render_to(tmp_path, "a", without=["jobs"])
    second = render_to(tmp_path, "b", without=["jobs"])
    assert digest(first) == digest(second)


def test_excluded_module_files_are_gone(tmp_path):
    out = render_to(tmp_path, "lean", without=["jobs"])
    assert not (out / "backend" / "app" / "endpoints" / "jobs.py").exists()
    assert not (out / "backend" / "app" / "models" / "job.py").exists()
    assert not (out / "backend" / "genesis" / "services" / "jobs.py").exists()
    assert not (out / "frontend" / "src" / "pages" / "Jobs.tsx").exists()
    assert (out / "backend" / "app" / "models" / "item.py").exists()


def test_excluded_module_leaves_no_infra_traces(tmp_path):
    out = render_to(tmp_path, "lean", without=["jobs"])
    for relative in (
        "Dockerfile",
        "deploy/supervisord.conf",
        "backend/pyproject.toml",
        "backend/settings.toml",
    ):
        assert "temporal" not in (out / relative).read_text(encoding="utf-8").lower()


def test_excluding_ai_strips_env_example(tmp_path):
    out = render_to(tmp_path, "noai", without=["ai", "rag"])
    assert "LLM_API_KEY" not in (out / ".env.example").read_text(encoding="utf-8")


def test_excluding_jobs_strips_docs(tmp_path):
    out = render_to(tmp_path, "nojobs", without=["jobs"])
    readme = (out / "README.md").read_text(encoding="utf-8")
    assert "restock_report" not in readme
    assert "/temporal/" not in readme
    agents = (out / "AGENTS.md").read_text(encoding="utf-8")
    assert "Add a background job" not in agents
    assert "Add a frontend page" in agents


def test_module_owned_migration_is_removed(tmp_path, monkeypatch):
    migration = TEMPLATE / "backend" / "migrations" / "099_module_owned_probe.py"
    migration.write_text("# probe\n", encoding="utf-8")
    manifest = load_modules(TEMPLATE / "modules")
    try:
        out = render_to(tmp_path, "withmig", without=[])
        assert (out / "backend" / "migrations" / "099_module_owned_probe.py").exists()

        manifest["jobs"]["files"].append("backend/migrations/099_module_owned_probe.py")
        monkeypatch.setattr("genesis_cli.cli.load_modules", lambda _path: manifest)
        out = render_to(tmp_path, "nomig", without=["jobs"])
        assert not (out / "backend" / "migrations" / "099_module_owned_probe.py").exists()
        assert (out / "backend" / "migrations" / "001_initial.py").exists()
    finally:
        migration.unlink(missing_ok=True)


def test_compose_topology_emits_services(tmp_path):
    out = render_to(tmp_path, "multi", topology="compose")
    compose = (out / "docker-compose.yml").read_text(encoding="utf-8")
    for service in ("postgres:", "valkey:", "temporal:", "temporal-ui:", "app:", "web:"):
        assert service in compose
    dockerfile = (out / "Dockerfile").read_text(encoding="utf-8")
    assert "ENTRYPOINT" not in dockerfile
    assert "postgresql" not in dockerfile
    assert not (out / "deploy" / "supervisord.conf").exists()
    assert "app:8000" in (out / "deploy" / "nginx.conf").read_text(encoding="utf-8")


def test_ci_workflow_is_rendered_verbatim(tmp_path):
    out = render_to(tmp_path, "withci", without=[])
    rendered = out / ".github" / "workflows" / "ci.yml"
    source = TEMPLATE / ".github" / "workflows" / "ci.yml"
    assert rendered.is_file()
    assert rendered.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")


def test_single_topology_keeps_everything(tmp_path):
    out = render_to(tmp_path, "single", topology="single")
    dockerfile = (out / "Dockerfile").read_text(encoding="utf-8")
    assert "ENTRYPOINT" in dockerfile
    assert (out / "deploy" / "supervisord.conf").exists()
    assert "127.0.0.1:8000" in (out / "deploy" / "nginx.conf").read_text(encoding="utf-8")
