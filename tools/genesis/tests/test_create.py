import argparse
from pathlib import Path

import pytest

from genesis_cli.cli import create, find_template
from genesis_cli.modules import ModuleError, load_modules
from genesis_cli.presets import excluded_for, load_presets, write_env

TEMPLATE = Path(__file__).resolve().parents[3]
PRESETS = load_presets(TEMPLATE / "modules")
AVAILABLE = set(load_modules(TEMPLATE / "modules"))


def make(tmp_path: Path, name: str, **overrides):
    args = argparse.Namespace(
        name=name,
        out=str(tmp_path / name),
        preset="full",
        without=[],
        topology="single",
        force=True,
        source=str(TEMPLATE),
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    assert create(args) == 0
    return Path(args.out)


def test_every_preset_names_only_real_modules():
    for name in PRESETS:
        assert excluded_for(PRESETS, AVAILABLE, name) == AVAILABLE - set(PRESETS[name]["modules"])


def test_unknown_preset_is_rejected():
    with pytest.raises(ModuleError, match="unknown preset"):
        excluded_for(PRESETS, AVAILABLE, "nope")


def test_full_preset_excludes_nothing():
    assert excluded_for(PRESETS, AVAILABLE, "full") == set()


def test_api_preset_drops_everything_but_cache():
    assert excluded_for(PRESETS, AVAILABLE, "api") == {
        "ai", "jobs", "analytics", "email", "storage", "realtime", "rag", "auth", "admin"
    }


def test_env_is_written_with_generated_secrets(tmp_path):
    (tmp_path / ".env.example").write_text(
        "APP_NAME=Genesis\nPOSTGRES_PASSWORD=genesis\nO2_ROOT_PASSWORD=genesis-admin\n"
        "AUTH_SECRET=genesis-dev-secret-change-me\n",
        encoding="utf-8",
    )
    write_env(tmp_path, "my-crm")
    written = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "APP_NAME=my-crm" in written
    assert "POSTGRES_PASSWORD=genesis\n" not in written
    assert "O2_ROOT_PASSWORD=genesis-admin" not in written
    assert "AUTH_SECRET=genesis-dev-secret-change-me" not in written


def test_created_project_is_self_describing(tmp_path):
    out = make(tmp_path, "ai-thing", preset="ai-app")
    assert (out / "genesis.json").is_file()
    project = (out / "PROJECT.md").read_text(encoding="utf-8")
    assert "| ai |" in project
    assert "| jobs |" not in project
    assert not (out / "backend" / "app" / "endpoints" / "jobs.py").exists()


def test_created_project_carries_its_own_manifests(tmp_path):
    out = make(tmp_path, "with-modules", preset="api")
    assert (out / "modules" / "kernel.toml").is_file()
    assert find_template(str(out)) == out


def test_created_project_excludes_the_generator(tmp_path):
    out = make(tmp_path, "no-tools")
    assert not (out / "tools").exists()


def test_extra_without_narrows_a_preset(tmp_path):
    out = make(tmp_path, "leaner", preset="saas", without=["analytics"])
    assert not (out / "backend" / "app" / "endpoints" / "analytics.py").exists()
    assert (out / "backend" / "app" / "endpoints" / "jobs.py").exists()
