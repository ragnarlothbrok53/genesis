from datetime import datetime

from pydantic import BaseModel, Field

from genesis import db


class Item(db.Model):
    name = db.Char(max_length=200)
    description = db.Text(null=True)
    created_at = db.DateTime(default=db.now)

    class Meta:
        table_name = "items"


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class ItemRead(BaseModel):
    id: int
    name: str
    description: str | None
    created_at: datetime
