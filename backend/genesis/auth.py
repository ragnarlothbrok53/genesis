from fastapi import Request

from genesis.core.identity import current_user as _passthrough_current_user

__all__ = ["current_user", "require_admin"]


def _local_user(request: Request) -> dict | None:
    try:
        from genesis.services import auth as auth_service
    except ImportError:
        return None
    return auth_service.verify_session(request)


def current_user(request: Request) -> dict | None:
    user = _local_user(request)
    if user is not None:
        return user
    return _passthrough_current_user(request)


def require_admin(request: Request) -> dict:
    from fastapi import HTTPException

    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthenticated")
    if "admin" not in user["roles"]:
        raise HTTPException(status_code=403, detail="Admin role required")
    return user
