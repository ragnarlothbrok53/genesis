import argparse
import json
import subprocess
from pathlib import Path

import pytest

from genesis_cli.cli import add_module, create, remove_module
from genesis_cli.sync import SyncError, add, remove

TEMPLATE = Path(__file__).resolve().parents[3]


def make_project(tmp_path: Path, name: str, preset: str = "api") -> Path:
    out = tmp_path / name
    args = argparse.Namespace(
        name=name,
        out=str(out),
        preset=preset,
        without=[],
        topology="single",
        force=True,
        source=str(TEMPLATE),
    )
    assert create(args) == 0
    return out


def test_add_restores_owned_files(tmp_path):
    project = make_project(tmp_path, "p1")
    assert not (project / "backend" / "app" / "endpoints" / "jobs.py").exists()

    result = add(project, TEMPLATE, "jobs")

    assert result["added"] == ["jobs"]
    assert (project / "backend" / "app" / "endpoints" / "jobs.py").exists()
    assert (project / "backend" / "app" / "models" / "job.py").exists()
    assert (project / "frontend" / "src" / "pages" / "Jobs.tsx").exists()


def test_add_reinserts_infra_markers(tmp_path):
    project = make_project(tmp_path, "p2")
    add(project, TEMPLATE, "jobs")

    dockerfile = (project / "Dockerfile").read_text(encoding="utf-8")
    assert "temporal" in dockerfile.lower()
    supervisord = (project / "deploy" / "supervisord.conf").read_text(encoding="utf-8")
    assert "temporal-server" in supervisord
    pyproject = (project / "backend" / "pyproject.toml").read_text(encoding="utf-8")
    assert "temporalio" in pyproject


def test_add_then_remove_round_trips_to_original(tmp_path):
    project = make_project(tmp_path, "p3")
    before = (project / "Dockerfile").read_text(encoding="utf-8")

    add(project, TEMPLATE, "jobs")
    remove(project, TEMPLATE, "jobs")

    after = (project / "Dockerfile").read_text(encoding="utf-8")
    assert before == after
    assert not (project / "backend" / "app" / "endpoints" / "jobs.py").exists()


def test_add_rejects_already_installed(tmp_path):
    project = make_project(tmp_path, "p4", preset="full")
    with pytest.raises(SyncError, match="already installed"):
        add(project, TEMPLATE, "jobs")


def test_add_rejects_unknown_module(tmp_path):
    project = make_project(tmp_path, "p5")
    with pytest.raises(SyncError, match="unknown module"):
        add(project, TEMPLATE, "nope")


def test_remove_rejects_not_installed(tmp_path):
    project = make_project(tmp_path, "p6")
    with pytest.raises(SyncError, match="not installed"):
        remove(project, TEMPLATE, "jobs")


def test_add_never_overwrites_a_locally_modified_infra_file(tmp_path):
    project = make_project(tmp_path, "p7")
    readme = project / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "\nmy custom note\n", encoding="utf-8")

    result = add(project, TEMPLATE, "jobs")

    assert "README.md" in result["infra_skipped"]
    assert "my custom note" in readme.read_text(encoding="utf-8")


def test_add_appends_env_keys_without_touching_secrets(tmp_path):
    project = make_project(tmp_path, "p8")
    original_secret = None
    for line in (project / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("POSTGRES_PASSWORD="):
            original_secret = line

    result = add(project, TEMPLATE, "ai")

    env = (project / ".env").read_text(encoding="utf-8")
    assert original_secret in env
    assert "LLM_API_KEY=" in env
    assert any(line.startswith("LLM_API_KEY") for line in result["env_appended"])


def test_add_does_not_duplicate_env_keys_already_present(tmp_path):
    project = make_project(tmp_path, "p9", preset="ai-app")
    add(project, TEMPLATE, "jobs")
    env = (project / ".env").read_text(encoding="utf-8")
    assert env.count("LLM_API_KEY=") == 1


def test_add_pulls_in_a_transitive_dependency(tmp_path, monkeypatch):
    project = make_project(tmp_path, "p10", preset="api")

    from genesis_cli import sync as sync_module
    from genesis_cli.modules import load_modules

    source_modules = load_modules(TEMPLATE / "modules")
    source_modules["extra"] = {
        "name": "extra",
        "requires": ["jobs"],
        "files": ["backend/app/models/summary.py"],
    }
    monkeypatch.setattr(sync_module, "load_modules", lambda _path: source_modules)

    result = add(project, TEMPLATE, "extra")

    assert set(result["added"]) == {"extra", "jobs"}
    assert (project / "backend" / "app" / "endpoints" / "jobs.py").exists()


def _install_fake_npm_module(monkeypatch, npm_deps: list[str]) -> dict:
    from genesis_cli import sync as sync_module
    from genesis_cli.modules import load_modules

    source_modules = load_modules(TEMPLATE / "modules")
    source_modules["authx"] = {
        "name": "authx",
        "requires": [],
        "npm_deps": npm_deps,
        "files": ["backend/genesis/services/llm.py"],
    }
    monkeypatch.setattr(sync_module, "load_modules", lambda _path: source_modules)
    return source_modules


def _fake_subprocess_run(monkeypatch, calls: list[list[str]]) -> None:
    from genesis_cli import sync as sync_module

    def fake_run(cmd, **_kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(sync_module.subprocess, "run", fake_run)


def test_add_module_with_npm_deps_updates_package_json_and_relocks(tmp_path, monkeypatch):
    project = make_project(tmp_path, "pnpm1")
    _install_fake_npm_module(monkeypatch, ["supertokens-auth-react@^0.35.0"])
    calls: list[list[str]] = []
    _fake_subprocess_run(monkeypatch, calls)

    result = add(project, TEMPLATE, "authx")

    package_json = json.loads((project / "frontend" / "package.json").read_text(encoding="utf-8"))
    assert package_json["dependencies"]["supertokens-auth-react"] == "^0.35.0"
    assert result["npm_added"] == ["supertokens-auth-react"]
    assert result["npm_relocked"] is True
    assert ["npm", "install", "--package-lock-only"] in calls


def test_remove_module_with_npm_deps_reverses_package_json(tmp_path, monkeypatch):
    project = make_project(tmp_path, "pnpm2")
    _install_fake_npm_module(monkeypatch, ["supertokens-auth-react@^0.35.0"])
    calls: list[list[str]] = []
    _fake_subprocess_run(monkeypatch, calls)
    before = (project / "frontend" / "package.json").read_text(encoding="utf-8")

    add(project, TEMPLATE, "authx")
    result = remove(project, TEMPLATE, "authx")

    after = (project / "frontend" / "package.json").read_text(encoding="utf-8")
    assert result["npm_removed"] == ["supertokens-auth-react"]
    assert result["npm_relocked"] is True
    assert json.loads(after) == json.loads(before)


def test_add_module_without_npm_deps_leaves_package_json_untouched(tmp_path):
    project = make_project(tmp_path, "pnpm3")
    before = (project / "frontend" / "package.json").read_text(encoding="utf-8")

    result = add(project, TEMPLATE, "jobs")

    after = (project / "frontend" / "package.json").read_text(encoding="utf-8")
    assert before == after
    assert result["npm_added"] == []
    assert result["npm_relocked"] is True


def test_cli_add_regenerates_docs(tmp_path):
    project = make_project(tmp_path, "p11")
    args = argparse.Namespace(target=str(project), source=str(TEMPLATE), module="jobs")
    assert add_module(args) == 0
    project_doc = (project / "PROJECT.md").read_text(encoding="utf-8")
    assert "| jobs |" in project_doc


def test_cli_remove_regenerates_docs(tmp_path):
    project = make_project(tmp_path, "p12", preset="full")
    remove_args = argparse.Namespace(target=str(project), source=str(TEMPLATE), module="jobs")
    assert remove_module(remove_args) == 0
    project_doc = (project / "PROJECT.md").read_text(encoding="utf-8")
    assert "| jobs |" not in project_doc
