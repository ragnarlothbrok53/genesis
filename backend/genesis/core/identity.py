import os

from fastapi import Request

_EMAIL_HEADER = "x-auth-request-email"
_USER_HEADER = "x-auth-request-user"
_ROLES_HEADER = "x-auth-request-roles"

_DEV_BYPASS = os.getenv("ENV_FOR_DYNACONF", "development").lower() == "development"


def _dev_user() -> dict:
    return {
        "email": "dev@local",
        "name": "Local Dev",
        "roles": ["admin"],
    }


def current_user(request: Request) -> dict | None:
    email = request.headers.get(_EMAIL_HEADER)
    if not email:
        return _dev_user() if _DEV_BYPASS else None

    roles_header = request.headers.get(_ROLES_HEADER, "")
    return {
        "email": email,
        "name": request.headers.get(_USER_HEADER, email),
        "roles": [r.strip() for r in roles_header.split(",") if r.strip()],
    }


def require_admin(request: Request) -> dict:
    from fastapi import HTTPException

    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthenticated")
    if "admin" not in user["roles"]:
        raise HTTPException(status_code=403, detail="Admin role required")
    return user
