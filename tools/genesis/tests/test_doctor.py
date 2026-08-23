from genesis_cli import doctor


def test_check_uv_present(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda name: "/usr/bin/uv" if name == "uv" else None)
    check = doctor.check_uv()
    assert check.present is True
    assert check.required is True


def test_check_uv_missing(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda name: None)
    check = doctor.check_uv()
    assert check.present is False
    assert "astral.sh" in check.message


def test_check_node_is_optional(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda name: None)
    check = doctor.check_node()
    assert check.present is False
    assert check.required is False
    assert "optional" in check.message


def test_check_node_present(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda name: "/usr/bin/node" if name == "node" else None)
    check = doctor.check_node()
    assert check.present is True


def test_check_npm_is_optional(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda name: None)
    check = doctor.check_npm()
    assert check.present is False
    assert check.required is False
    assert "optional" in check.message


def test_check_npm_present(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda name: "/usr/bin/npm" if name == "npm" else None)
    check = doctor.check_npm()
    assert check.present is True


def test_check_docker_is_optional(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda name: None)
    check = doctor.check_docker()
    assert check.present is False
    assert check.required is False
    assert "--local" in check.message


def test_check_docker_present(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda name: "/usr/bin/docker" if name == "docker" else None)
    check = doctor.check_docker()
    assert check.present is True


def test_check_flyctl_is_optional(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda name: None)
    check = doctor.check_flyctl()
    assert check.present is False
    assert check.required is False
    assert "deploy" in check.message


def test_check_flyctl_present(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda name: "/usr/bin/flyctl" if name == "flyctl" else None)
    check = doctor.check_flyctl()
    assert check.present is True


def test_run_checks_returns_uv_and_node():
    names = [check.name for check in doctor.run_checks()]
    assert names == ["uv", "node", "npm", "docker", "flyctl"]
