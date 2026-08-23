from fastapi import HTTPException, Request

from app.models.permission import PermissionRule
from genesis.auth import current_user


def enforce(request: Request) -> None:
    rules = [
        rule
        for rule in PermissionRule.select()
        if request.url.path.startswith(rule.path) and rule.method in ("*", request.method)
    ]
    if not rules:
        return

    user = current_user(request)
    user_roles = set(user["roles"]) if user else set()
    if any(rule.role in user_roles for rule in rules):
        return

    raise HTTPException(status_code=403, detail="Not permitted")


def check() -> bool:
    return True
