from fastapi import HTTPException

from app.models.item import Item, ItemCreate, ItemRead
from genesis import db, router

api = router("/items")


@api.get("", response_model=list[ItemRead])
def list_items():
    return list(Item.select().order_by(Item.id).dicts())


@api.post("", response_model=ItemRead, status_code=201)
def create_item(payload: ItemCreate):
    return db.to_dict(Item.create(**payload.model_dump()))


@api.delete("/{item_id}", status_code=204)
def delete_item(item_id: int):
    if not Item.delete_by_id(item_id):
        raise HTTPException(status_code=404, detail="Item not found")
