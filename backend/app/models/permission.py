from datetime import datetime

from pydantic import BaseModel, Field

from genesis import db


class PermissionRule(db.Model):
    method = db.Char(max_length=10, default="*")
    path = db.Char(max_length=200)
    role = db.Char(max_length=100)
    created_at = db.DateTime(default=db.now)

    class Meta:
        table_name = "permission_rules"
        indexes = ((("method", "path", "role"), True),)


class PermissionRuleCreate(BaseModel):
    method: str = Field(default="*", max_length=10)
    path: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=100)


class PermissionRuleRead(BaseModel):
    id: int
    method: str
    path: str
    role: str
    created_at: datetime
