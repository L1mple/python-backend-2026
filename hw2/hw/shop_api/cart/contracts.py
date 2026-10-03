from __future__ import annotations

from pydantic import BaseModel

from store.cart.models import CartEntity
from store.cart import queries as cart_queries
from store.item import queries as item_queries


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
        items: list[CartItemResponse] = []
        for item_id, quantity in entity.items.items():
            item = item_queries.get(item_id)
            if item is None:
                continue
            items.append(
                CartItemResponse(
                    id=item.id,
                    name=item.name,
                    quantity=quantity,
                    available=not item.deleted,
                )
            )
        return CartResponse(
            id=entity.id,
            items=items,
            price=cart_queries.total_price(entity),
        )
