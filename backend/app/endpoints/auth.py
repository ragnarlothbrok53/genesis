from fastapi import HTTPException, Response

from app.models.user import User, UserLogin, UserRead, UserSignup
from genesis import db, router
from genesis.core.config import settings
from genesis.services.auth import COOKIE_NAME, create_token, hash_password, verify_password

api = router("/auth")


def _to_read(user: User) -> dict:
    payload = db.to_dict(user)
    payload["roles"] = [role for role in user.roles.split(",") if role]
    return payload


def _bootstrap_roles(email: str) -> str:
    admins = {e.strip().lower() for e in settings.get("ADMIN_EMAILS", "").split(",") if e.strip()}
    return "admin" if email.lower() in admins else ""


@api.post("/signup", response_model=UserRead, status_code=201)
def signup(payload: UserSignup, response: Response):
    if User.select().where(User.email == payload.email).exists():
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User.create(
        email=payload.email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        roles=_bootstrap_roles(payload.email),
    )
    response.set_cookie(COOKIE_NAME, create_token(user), httponly=True, samesite="lax")
    return _to_read(user)


@api.post("/login", response_model=UserRead)
def login(payload: UserLogin, response: Response):
    user = User.get_or_none(User.email == payload.email)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.active:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    response.set_cookie(COOKIE_NAME, create_token(user), httponly=True, samesite="lax")
    return _to_read(user)


@api.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)
