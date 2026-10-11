from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from store.item.models import ItemEntity


class ItemResponse(BaseModel):
    id: int
    name: str
    price: float
    deleted: bool

    @staticmethod
    def from_entity(entity: ItemEntity) -> "ItemResponse":
        return ItemResponse(
            id=entity.id,
            name=entity.name,
            price=entity.price,
            deleted=entity.deleted,
        )


class ItemRequest(BaseModel):
    name: str
    price: float = Field(ge=0)


class PutItemRequest(BaseModel):
    name: str
    price: float = Field(ge=0)


class PatchItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    price: float | None = Field(default=None, ge=0)
