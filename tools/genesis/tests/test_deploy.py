import subprocess

import pytest

from genesis_cli import deploy


class Recorder:
    def __init__(self, returncode: int = 0):
        self.calls: list[list[str]] = []
        self.returncode = returncode

    def __call__(self, command, **kwargs):
        self.calls.append(command)
        return subprocess.CompletedProcess(command, self.returncode, "", "")


def _write_kernel(root, port=80):
    modules_dir = root / "modules"
    modules_dir.mkdir(parents=True, exist_ok=True)
    (modules_dir / "kernel.toml").write_text(
        f'[[process]]\nname = "fastapi"\nport = 8000\n\n'
        f'[[process]]\nname = "nginx"\nport = {port}\n',
        encoding="utf-8",
    )


def test_app_name_reads_env_and_slugifies(tmp_path):
    (tmp_path / ".env").write_text("APP_NAME=My Cool App!\n", encoding="utf-8")
    assert deploy.app_name(tmp_path) == "my-cool-app"


def test_app_name_falls_back_to_directory_name(tmp_path):
    project = tmp_path / "Widget Factory"
    project.mkdir()
    assert deploy.app_name(project) == "widget-factory"


def test_render_fly_toml_uses_nginx_port_from_kernel(tmp_path):
    _write_kernel(tmp_path, port=80)
    content = deploy.render_fly_toml(tmp_path, "my-app")
    assert 'app = "my-app"' in content
    assert "internal_port = 80" in content


def test_render_fly_toml_defaults_port_without_kernel(tmp_path):
    content = deploy.render_fly_toml(tmp_path, "my-app")
    assert "internal_port = 80" in content


def test_ensure_fly_toml_writes_when_missing(tmp_path):
    _write_kernel(tmp_path)
    path = deploy.ensure_fly_toml(tmp_path, "my-app")
    assert path == tmp_path / "fly.toml"
    assert path.is_file()
    assert 'app = "my-app"' in path.read_text(encoding="utf-8")


def test_ensure_fly_toml_does_not_overwrite_existing(tmp_path):
    existing = tmp_path / "fly.toml"
    existing.write_text("app = \"already-configured\"\n", encoding="utf-8")
    path = deploy.ensure_fly_toml(tmp_path, "my-app")
    assert path.read_text(encoding="utf-8") == 'app = "already-configured"\n'


def test_dry_run_generates_toml_and_prints_command_without_deploying(
    tmp_path, monkeypatch, capsys
):
    _write_kernel(tmp_path)
    recorder = Recorder()
    monkeypatch.setattr(deploy.subprocess, "run", recorder)
    monkeypatch.setattr(deploy.shutil, "which", lambda _name: None)

    code = deploy.deploy(tmp_path, dry_run=True, name="my-app")

    assert code == 0
    assert recorder.calls == []
    assert (tmp_path / "fly.toml").is_file()
    output = capsys.readouterr().out
    assert "flyctl deploy" in output
    assert "--app my-app" in output


def test_missing_flyctl_raises_clear_error(tmp_path, monkeypatch):
    _write_kernel(tmp_path)
    monkeypatch.setattr(deploy.shutil, "which", lambda _name: None)

    with pytest.raises(deploy.DeployError, match="flyctl not found"):
        deploy.deploy(tmp_path, name="my-app")


def test_deploy_shells_out_to_flyctl_when_present(tmp_path, monkeypatch):
    _write_kernel(tmp_path)
    recorder = Recorder()
    monkeypatch.setattr(deploy.subprocess, "run", recorder)
    monkeypatch.setattr(deploy.shutil, "which", lambda _name: "/usr/local/bin/flyctl")

    code = deploy.deploy(tmp_path, name="my-app")

    assert code == 0
    assert recorder.calls[-1][:2] == ["flyctl", "deploy"]
    assert "--app" in recorder.calls[-1]
    assert "my-app" in recorder.calls[-1]
