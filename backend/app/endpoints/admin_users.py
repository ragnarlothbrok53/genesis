from fastapi import Depends, HTTPException

from app.models.user import User, UserAdminRead, UserUpdateRoles
from genesis import db, router
from genesis.auth import require_admin

api = router("/admin/users")


def _to_read(user: User) -> dict:
    payload = db.to_dict(user)
    payload["roles"] = [role for role in user.roles.split(",") if role]
    return payload


@api.get("", response_model=list[UserAdminRead], dependencies=[Depends(require_admin)])
def list_users():
    return [_to_read(user) for user in User.select().order_by(User.id)]


@api.patch("/{user_id}", response_model=UserAdminRead, dependencies=[Depends(require_admin)])
def update_roles(user_id: int, payload: UserUpdateRoles):
    user = User.get_or_none(User.id == user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.roles = ",".join(payload.roles)
    user.save()
    return _to_read(user)


@api.post("/{user_id}/deactivate", response_model=UserAdminRead)
def deactivate_user(user_id: int, admin=Depends(require_admin)):
    user = User.get_or_none(User.id == user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.email == admin["email"]:
        raise HTTPException(status_code=400, detail="You cannot deactivate yourself")
    user.active = False
    user.save()
    return _to_read(user)


@api.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, admin=Depends(require_admin)):
    user = User.get_or_none(User.id == user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.email == admin["email"]:
        raise HTTPException(status_code=400, detail="You cannot delete yourself")
    user.delete_instance()
