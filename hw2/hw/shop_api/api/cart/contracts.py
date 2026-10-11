from pydantic import BaseModel

from shop_api import store
from shop_api.store import CartEntity


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
    def from_entity(entity: CartEntity) -> 'CartResponse':
        items = []
        price = 0.0

        for item_id, quantity in entity.items.items():
            item = store.get_item(item_id)
            if item is None:
                continue
            items.append(
                CartItemResponse(
                    id=item_id,
                    name=item.info.name,
                    quantity=quantity,
                    available=not item.info.deleted,
                )
            )
            price += item.info.price * quantity

        return CartResponse(id=entity.id, items=items, price=price)
