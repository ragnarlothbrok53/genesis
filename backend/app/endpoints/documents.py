from fastapi import HTTPException

from app.models.document import (
    Document,
    DocumentCreate,
    DocumentRead,
    DocumentSearchRequest,
    DocumentSearchResult,
)
from genesis import ai, db, router

api = router("/documents")


@api.get("", response_model=list[DocumentRead])
def list_documents():
    return list(Document.select().order_by(Document.id).dicts())


@api.post("", response_model=DocumentRead, status_code=201)
def create_document(payload: DocumentCreate):
    try:
        embedding = ai.embed(payload.content)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Embedding error: {exc}") from exc
    return db.to_dict(Document.create(content=payload.content, embedding=embedding))


@api.post("/search", response_model=list[DocumentSearchResult])
def search_documents(payload: DocumentSearchRequest):
    try:
        return ai.similarity_search(Document, payload.query, k=payload.k)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Search error: {exc}") from exc
