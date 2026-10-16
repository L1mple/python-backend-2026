from pydantic import BaseModel
from ...store import queries
from ...store.models import Cart


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
    def from_entity(cart: Cart):
        items = []
        for item_id, quantity in cart.item_id_to_count.items():
            item = queries.get_item(item_id)
            items.append(
                CartItemResponse(
                    id=item.id,
                    name=item.name,
                    quantity=quantity,
                    available=not item.deleted,
                )
            )
        return CartResponse(
            id=cart.id,
            items=items,
            price=queries.cart_price(cart),
        )
