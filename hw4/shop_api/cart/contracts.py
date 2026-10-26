from __future__ import annotations

from pydantic import BaseModel

from store.cart.models import CartEntity


class CartItemResponse(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class CartResponse(BaseModel):
    id: int
    items: list[CartItemResponse]
    price: float

    @staticmethod
    def from_entity(entity: CartEntity) -> "CartResponse":
        return CartResponse(
            id=entity.id,
            items=[
                CartItemResponse(
                    id=item.id,
                    name=item.name,
                    quantity=item.quantity,
                    available=item.available,
                )
                for item in entity.items
            ],
            price=entity.price,
        )
