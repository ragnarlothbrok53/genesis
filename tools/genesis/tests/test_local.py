import argparse
import subprocess

import pytest

from genesis_cli import cli, local
from genesis_cli.doctor import Check


class Recorder:
    def __init__(self, returncode: int = 0):
        self.calls: list[list[str]] = []
        self.returncode = returncode

    def __call__(self, command, **kwargs):
        self.calls.append(command)
        return subprocess.CompletedProcess(command, self.returncode, "", "")


@pytest.fixture
def recorder(monkeypatch):
    recorder = Recorder()
    monkeypatch.setattr(local.subprocess, "run", recorder)
    return recorder


def _checks(uv_present, node_present):
    return [
        Check("uv", uv_present, True, "install uv from astral.sh"),
        Check("node", node_present, False, "optional, needed only for frontend dev"),
    ]


def test_dev_parser_accepts_local_flag():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command")
    dev_parser = commands.add_parser("dev")
    dev_parser.add_argument("--no-build", action="store_true")
    dev_parser.add_argument("--local", action="store_true")
    args = parser.parse_args(["dev", "--local"])
    assert args.local is True


def test_uv_missing_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(local, "run_checks", lambda: _checks(False, True))
    with pytest.raises(local.LocalError, match="uv"):
        local.dev_local(tmp_path)


def test_dist_already_built_is_used_without_node(monkeypatch, recorder, tmp_path):
    dist = tmp_path / "frontend" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<html></html>")
    monkeypatch.setattr(local, "run_checks", lambda: _checks(True, False))

    code = local.dev_local(tmp_path)

    assert code == 0
    assert str(dist) in recorder.calls[-1]


def test_missing_dist_builds_when_node_present(monkeypatch, tmp_path):
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        if command[:2] == ["npm", "run"]:
            dist = frontend / "dist"
            dist.mkdir(parents=True, exist_ok=True)
            (dist / "index.html").write_text("<html></html>")
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(local.subprocess, "run", fake_run)
    monkeypatch.setattr(local.shutil, "which", lambda _name: "npm")
    monkeypatch.setattr(local, "run_checks", lambda: _checks(True, True))

    code = local.dev_local(tmp_path)

    assert code == 0
    assert any(command[:2] == ["npm", "run"] for command in calls)
    assert str(frontend / "dist") in calls[-1]


def test_missing_dist_and_node_skips_frontend(monkeypatch, recorder, tmp_path):
    monkeypatch.setattr(local, "run_checks", lambda: _checks(True, False))

    code = local.dev_local(tmp_path)

    assert code == 0
    assert recorder.calls[-1][-1] == ""


def test_frontend_build_failure_raises(monkeypatch, tmp_path):
    frontend = tmp_path / "frontend"
    (frontend / "node_modules").mkdir(parents=True)
    monkeypatch.setattr(local, "run_checks", lambda: _checks(True, True))
    monkeypatch.setattr(local.shutil, "which", lambda _name: "npm")
    monkeypatch.setattr(local.subprocess, "run", Recorder(returncode=1))

    with pytest.raises(local.LocalError, match="npm run build"):
        local.dev_local(tmp_path)


def test_npm_install_failure_raises(monkeypatch, tmp_path):
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    monkeypatch.setattr(local, "run_checks", lambda: _checks(True, True))
    monkeypatch.setattr(local.shutil, "which", lambda _name: "npm")
    monkeypatch.setattr(local.subprocess, "run", Recorder(returncode=1))

    with pytest.raises(local.LocalError, match="npm install"):
        local.dev_local(tmp_path)


def test_runs_npm_install_when_node_modules_missing(monkeypatch, tmp_path):
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        if command[1:] == ["install"]:
            (frontend / "node_modules").mkdir()
        if command[1:3] == ["run", "build"]:
            dist = frontend / "dist"
            dist.mkdir(parents=True, exist_ok=True)
            (dist / "index.html").write_text("<html></html>")
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(local.subprocess, "run", fake_run)
    monkeypatch.setattr(local.shutil, "which", lambda _name: "npm")
    monkeypatch.setattr(local, "run_checks", lambda: _checks(True, True))

    code = local.dev_local(tmp_path)

    assert code == 0
    assert any(command[1:] == ["install"] for command in calls)


def test_skips_npm_install_when_node_modules_present(monkeypatch, tmp_path):
    frontend = tmp_path / "frontend"
    (frontend / "node_modules").mkdir(parents=True)
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        if command[1:3] == ["run", "build"]:
            dist = frontend / "dist"
            dist.mkdir(parents=True, exist_ok=True)
            (dist / "index.html").write_text("<html></html>")
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(local.subprocess, "run", fake_run)
    monkeypatch.setattr(local.shutil, "which", lambda _name: "npm")
    monkeypatch.setattr(local, "run_checks", lambda: _checks(True, True))

    code = local.dev_local(tmp_path)

    assert code == 0
    assert not any(command[1:] == ["install"] for command in calls)


def test_missing_npm_binary_raises(monkeypatch, tmp_path):
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    monkeypatch.setattr(local, "run_checks", lambda: _checks(True, True))
    monkeypatch.setattr(local.shutil, "which", lambda _name: None)

    with pytest.raises(local.LocalError, match="npm not found"):
        local.dev_local(tmp_path)


def test_run_dev_dispatches_to_local_mode(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "find_template", lambda _source: tmp_path)
    called = {}

    def fake_dev_local(root):
        called["root"] = root
        return 0

    monkeypatch.setattr(cli, "dev_local", fake_dev_local)
    args = argparse.Namespace(source=None, local=True, no_build=False)

    assert cli.run_dev(args) == 0
    assert called["root"] == tmp_path
