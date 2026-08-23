from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from genesis import db


class User(db.Model):
    email = db.Char(max_length=200, unique=True)
    name = db.Char(max_length=200)
    password_hash = db.Char(max_length=200)
    roles = db.Char(max_length=200, default="")
    active = db.Bool(default=True)
    created_at = db.DateTime(default=db.now)

    class Meta:
        table_name = "users"


class UserSignup(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8, max_length=200)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserRead(BaseModel):
    id: int
    email: str
    name: str
    roles: list[str]


class UserUpdateRoles(BaseModel):
    roles: list[str]


class UserAdminRead(BaseModel):
    id: int
    email: str
    name: str
    roles: list[str]
    active: bool
    created_at: datetime
