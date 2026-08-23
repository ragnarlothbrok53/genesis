import subprocess

import pytest

from genesis_cli import ops


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
    monkeypatch.setattr(ops.subprocess, "run", recorder)
    monkeypatch.setattr(ops.shutil, "which", lambda _name: "/usr/bin/docker")
    return recorder


def test_dev_builds_then_waits(recorder, monkeypatch, tmp_path):
    monkeypatch.setattr(ops, "_wait_for_health", lambda *_args, **_kwargs: True)
    assert ops.dev(tmp_path) == 0
    assert recorder.calls[-1][-3:] == ["up", "-d", "--build"]


def test_dev_can_skip_the_build(recorder, monkeypatch, tmp_path):
    monkeypatch.setattr(ops, "_wait_for_health", lambda *_args, **_kwargs: True)
    ops.dev(tmp_path, build=False)
    assert "--build" not in recorder.calls[-1]


def test_dev_fails_when_never_healthy(recorder, monkeypatch, tmp_path):
    monkeypatch.setattr(ops, "_wait_for_health", lambda *_args, **_kwargs: False)
    assert ops.dev(tmp_path) == 1


def test_build_does_not_start_anything(recorder, tmp_path):
    ops.build(tmp_path)
    assert recorder.calls[-1][-1:] == ["build"]
    assert "up" not in recorder.calls[-1]


def test_down_stops_both_profiles(recorder, tmp_path):
    ops.down(tmp_path)
    assert recorder.calls[-1][-3:] == ["--profile", "prod", "down"]


def test_restart_defaults_through_supervisorctl(recorder, tmp_path):
    ops.restart(tmp_path, "fastapi")
    assert recorder.calls[-1][-4:] == ["app_dev", "supervisorctl", "restart", "fastapi"]


def test_migrate_uses_the_loader_not_the_models_package(recorder, tmp_path):
    ops.migrate(tmp_path, "add widgets")
    script = recorder.calls[-1][-1]
    assert "from genesis.loader import load_models" in script
    assert "import app.models" not in script
    assert "add widgets" in script


def test_migrate_rejects_quotes_that_would_break_the_shell(recorder, tmp_path):
    with pytest.raises(ops.OpsError, match="quotes"):
        ops.migrate(tmp_path, 'add "widgets"')


def test_missing_docker_is_reported_clearly(monkeypatch, tmp_path):
    monkeypatch.setattr(ops.shutil, "which", lambda _name: None)
    with pytest.raises(ops.OpsError, match="docker not found"):
        ops.dev(tmp_path)


def test_stopped_docker_is_reported_clearly(monkeypatch, tmp_path):
    monkeypatch.setattr(ops.shutil, "which", lambda _name: "/usr/bin/docker")
    monkeypatch.setattr(ops.subprocess, "run", Recorder(returncode=1))
    with pytest.raises(ops.OpsError, match="not running"):
        ops.dev(tmp_path)
