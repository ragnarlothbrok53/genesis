import asyncio
import logging
from email.message import EmailMessage

from genesis.core.config import settings

logger = logging.getLogger(__name__)

_aiosmtplib = None


def _get_aiosmtplib():
    global _aiosmtplib
    if _aiosmtplib is None:
        import aiosmtplib

        _aiosmtplib = aiosmtplib
    return _aiosmtplib


def _smtp() -> bool:
    return settings.EMAIL_BACKEND == "smtp"


def check() -> bool:
    if not _smtp():
        return True
    return bool(settings.get("SMTP_HOST") and settings.get("EMAIL_FROM"))


def _send_smtp(to: str, subject: str, body: str) -> None:
    host = settings.get("SMTP_HOST")
    from_addr = settings.get("EMAIL_FROM")
    if not host or not from_addr:
        raise RuntimeError(
            "SMTP not configured; set SMTP_HOST and EMAIL_FROM in .env "
            "(or switch EMAIL_BACKEND to console)"
        )

    message = EmailMessage()
    message["From"] = from_addr
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    asyncio.run(
        _get_aiosmtplib().send(
            message,
            hostname=host,
            port=settings.get("SMTP_PORT", 587),
            username=settings.get("SMTP_USER") or None,
            password=settings.get("SMTP_PASSWORD") or None,
            start_tls=True,
        )
    )


def send(to: str, subject: str, body: str) -> None:
    if _smtp():
        _send_smtp(to, subject, body)
        return
    logger.info("email to=%s subject=%s body=%s", to, subject, body)
