import pytest

from genesis.core.config import settings
from genesis.services import email


@pytest.fixture
def console_email(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_BACKEND", "console")
    yield email


@pytest.fixture
def smtp_email(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_BACKEND", "smtp")
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    monkeypatch.setattr(settings, "EMAIL_FROM", "")
    yield email


def test_console_backend_logs_the_email(console_email, caplog):
    with caplog.at_level("INFO", logger="genesis.services.email"):
        console_email.send("user@example.com", "Welcome", "Hello there")
    assert "user@example.com" in caplog.text
    assert "Welcome" in caplog.text


def test_console_backend_check_reports_healthy(console_email):
    assert console_email.check() is True


def test_smtp_backend_without_config_raises_clear_error(smtp_email):
    with pytest.raises(RuntimeError, match="SMTP not configured"):
        smtp_email.send("user@example.com", "Welcome", "Hello there")


def test_smtp_backend_without_config_reports_unhealthy(smtp_email):
    assert smtp_email.check() is False
