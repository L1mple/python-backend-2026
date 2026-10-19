from __future__ import annotations
from shop_api.store.models import Item
from pydantic import BaseModel, ConfigDict


class ItemResponse(BaseModel):
    id: int
    name: str
    price: float
    deleted: bool

    @staticmethod
    def from_entity(item: Item) -> ItemResponse:
        return ItemResponse(
            id=item.id,
            name=item.name,
            price=float(item.price),
            deleted=item.deleted,
        )


class ItemRequest(BaseModel):
    name: str
    price: float


class PatchItemRequest(BaseModel):
    name: str | None = None
    price: float | None = None

    model_config = ConfigDict(extra="forbid")