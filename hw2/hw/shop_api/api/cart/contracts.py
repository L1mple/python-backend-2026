from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from shop_api.store.cart.models import (
    CartItem,
    CartEntity
)


class CreateCartResponse(BaseModel):
    id: int


class CartItemResponse(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool

    @staticmethod
    def from_entity(entity: CartItem) -> CartItemResponse:
        return CartItemResponse(
            id=entity.info.id,
            name=entity.info.info.name,
            quantity=entity.quantity,
            available=not entity.info.info.deleted
        )


class CartResponse(BaseModel):
    id: int
    items: list[CartItemResponse]
    price: float

    @staticmethod
    def from_entity(entity: CartEntity) -> CartResponse:
        return CartResponse(
            id=entity.id,
            items=[CartItemResponse.from_entity(item) for item in entity.info.items],
            price=entity.info.price
        )


class CartListRequest(BaseModel):
    offset: int = 0
    limit: int = 10
    min_price: float | None = None
    max_price: float | None = None
    min_quantity: int | None = None
    max_quantity: int | None = None
