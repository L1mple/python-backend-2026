from __future__ import annotations

from pydantic import BaseModel

from shop_api.store.models import CartEntity, CartItem


class CartItemResponse(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool

    @staticmethod
    def from_item(item: CartItem) -> CartItemResponse:
        return CartItemResponse(
            id=item.id,
            name=item.name,
            quantity=item.quantity,
            available=item.available,
        )


class CartResponse(BaseModel):
    id: int
    items: list[CartItemResponse]
    price: float

    @staticmethod
    def from_entity(entity: CartEntity) -> CartResponse:
        return CartResponse(
            id=entity.id,
            items=[CartItemResponse.from_item(item) for item in entity.items],
            price=entity.price,
        )
