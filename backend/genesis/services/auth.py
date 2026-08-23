import logging
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from genesis.core.config import settings

logger = logging.getLogger(__name__)

COOKIE_NAME = "genesis_session"
_ALGORITHM = "HS256"


def configured() -> bool:
    return bool(settings.get("AUTH_SECRET"))


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def _roles_list(roles: str) -> list[str]:
    return [role for role in roles.split(",") if role]


def create_token(user) -> str:
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "name": user.name,
        "roles": _roles_list(user.roles),
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    return jwt.encode(payload, settings.get("AUTH_SECRET"), algorithm=_ALGORITHM)


def verify_session(request) -> dict | None:
    if not configured():
        return None

    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None

    try:
        payload = jwt.decode(token, settings.get("AUTH_SECRET"), algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        logger.warning("auth session token invalid", exc_info=True)
        return None

    return {
        "id": int(payload["sub"]),
        "email": payload["email"],
        "name": payload["name"],
        "roles": payload["roles"],
    }


def check() -> bool:
    return configured()
