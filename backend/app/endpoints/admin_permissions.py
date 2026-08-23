from fastapi import Depends, HTTPException, Request

from app.models.permission import PermissionRule, PermissionRuleCreate, PermissionRuleRead
from genesis import db, router
from genesis.auth import require_admin

api = router("/admin/permissions")


@api.get("", response_model=list[PermissionRuleRead], dependencies=[Depends(require_admin)])
def list_rules():
    return list(PermissionRule.select().order_by(PermissionRule.id).dicts())


@api.get("/routes", response_model=list[str], dependencies=[Depends(require_admin)])
def list_routes(request: Request):
    return sorted(getattr(request.app.state, "mounted_routes", []))


@api.post(
    "", response_model=PermissionRuleRead, status_code=201, dependencies=[Depends(require_admin)]
)
def create_rule(payload: PermissionRuleCreate):
    return db.to_dict(PermissionRule.create(**payload.model_dump()))


@api.delete("/{rule_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_rule(rule_id: int):
    if not PermissionRule.delete_by_id(rule_id):
        raise HTTPException(status_code=404, detail="Rule not found")
