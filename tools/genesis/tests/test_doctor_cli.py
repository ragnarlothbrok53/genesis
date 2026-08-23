import argparse

from genesis_cli import cli, doctor


def _checks(uv_present, node_present):
    return [
        doctor.Check("uv", uv_present, True, "install uv from astral.sh"),
        doctor.Check("node", node_present, False, "optional, needed only for frontend dev with hot reload"),
    ]


def test_doctor_passes_when_uv_present(monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_checks", lambda: _checks(True, True))
    code = cli.doctor(argparse.Namespace())
    assert code == 0
    out = capsys.readouterr().out
    assert "uv" in out
    assert "node" in out


def test_doctor_fails_when_uv_missing_and_declines_install(monkeypatch):
    monkeypatch.setattr(cli, "run_checks", lambda: _checks(False, False))
    monkeypatch.setattr(cli, "_is_interactive", lambda: False)
    code = cli.doctor(argparse.Namespace())
    assert code == 1


def test_doctor_installs_uv_when_confirmed(monkeypatch):
    monkeypatch.setattr(cli, "run_checks", lambda: _checks(False, True))
    monkeypatch.setattr(cli, "_is_interactive", lambda: True)
    monkeypatch.setattr(cli.ux, "confirm", lambda *a, **k: True)
    monkeypatch.setattr(cli, "install_uv", lambda: 0)
    code = cli.doctor(argparse.Namespace())
    assert code == 0


def test_doctor_reports_failure_when_install_fails(monkeypatch):
    monkeypatch.setattr(cli, "run_checks", lambda: _checks(False, True))
    monkeypatch.setattr(cli, "_is_interactive", lambda: True)
    monkeypatch.setattr(cli.ux, "confirm", lambda *a, **k: True)
    monkeypatch.setattr(cli, "install_uv", lambda: 1)
    code = cli.doctor(argparse.Namespace())
    assert code == 1
