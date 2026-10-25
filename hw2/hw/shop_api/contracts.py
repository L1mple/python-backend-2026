from __future__ import annotations

from pydantic import BaseModel, ConfigDict, NonNegativeFloat

from .storage.models import Cart, CartItem, Item


class ItemResponse(BaseModel):
    id: int
    name: str
    price: float
    deleted: bool

    @staticmethod
    def from_entity(entity: Item) -> ItemResponse:
        return ItemResponse(
            id=entity.id,
            name=entity.name,
            price=entity.price,
            deleted=entity.deleted
        )


class ItemRequest(BaseModel):
    name: str
    price: NonNegativeFloat


class PatchItemRequest(BaseModel):
    name: str | None = None
    price: NonNegativeFloat | None = None

    model_config = ConfigDict(extra="forbid")


class CartItemResponse(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool

    @staticmethod
    def from_entity(entity: CartItem) -> CartItemResponse:
        return CartItemResponse(
            id=entity.id,
            name=entity.name,
            quantity=entity.quantity,
            available=entity.available
        )


class CartResponse(BaseModel):
    id: int
    items: list[CartItemResponse]
    price: float

    @staticmethod
    def from_entity(entity: Cart) -> CartResponse:
        return CartResponse(
            id=entity.id,
            items=[CartItemResponse.from_entity(item) for item in entity.items],
            price=entity.price
        )


class CartIdResponse(BaseModel):
    id: int
