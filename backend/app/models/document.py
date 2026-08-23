from datetime import datetime

from pgvector.peewee import VectorField
from pydantic import BaseModel, Field

from genesis import db

EMBEDDING_DIMENSIONS = 1536


class Document(db.Model):
    content = db.Text()
    embedding = VectorField(dimensions=EMBEDDING_DIMENSIONS)
    created_at = db.DateTime(default=db.now)

    class Meta:
        table_name = "documents"


class DocumentCreate(BaseModel):
    content: str = Field(min_length=1)


class DocumentRead(BaseModel):
    id: int
    content: str
    created_at: datetime


class DocumentSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    k: int = Field(default=5, ge=1, le=50)


class DocumentSearchResult(BaseModel):
    id: int
    content: str
    created_at: datetime
