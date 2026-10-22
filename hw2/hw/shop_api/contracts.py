from __future__ import annotations

from pydantic import BaseModel, ConfigDict, NonNegativeFloat

from shop_api.storage import Item


class ItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    price: NonNegativeFloat


class ItemPatchRequest(BaseModel):
    # Лишние поля (в том числе deleted) дают 422
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    price: NonNegativeFloat | None = None


class ItemResponse(BaseModel):
    id: int
    name: str
    price: float
    deleted: bool

    @staticmethod
    def from_item(item: Item) -> ItemResponse:
        return ItemResponse(
            id=item.id,
            name=item.name,
            price=item.price,
            deleted=item.deleted,
        )


class CartCreatedResponse(BaseModel):
    id: int


class CartItemResponse(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class CartResponse(BaseModel):
    id: int
    items: list[CartItemResponse]
    price: float
