"""In-memory shop data. Cart views reflect current item names and prices."""

from itertools import count
from math import fsum

from .models import Cart, CartItem, Item, ItemData, ItemPatch


class ShopStore:
    def __init__(self) -> None:
        self.items: dict[int, Item] = {}
        self.carts: dict[int, dict[int, int]] = {}
        self._item_ids = count(1)
        self._cart_ids = count(1)

    def create_item(self, data: ItemData) -> Item:
        item = Item(id=next(self._item_ids), **data.model_dump())
        self.items[item.id] = item
        return item

    def replace_item(self, item_id: int, data: ItemData) -> Item:
        item = Item(id=item_id, **data.model_dump())
        self.items[item_id] = item
        return item

    def patch_item(self, item_id: int, data: ItemPatch) -> Item:
        item = self.items[item_id]
        if data.name is not None:
            item.name = data.name
        if data.price is not None:
            item.price = data.price
        return item

    def create_cart(self) -> int:
        cart_id = next(self._cart_ids)
        self.carts[cart_id] = {}
        return cart_id

    def get_cart(self, cart_id: int) -> Cart:
        quantities = self.carts[cart_id]
        return Cart(
            id=cart_id,
            items=[
                CartItem(
                    id=item_id,
                    name=self.items[item_id].name,
                    quantity=quantity,
                    available=not self.items[item_id].deleted,
                )
                for item_id, quantity in quantities.items()
            ],
            price=fsum(
                self.items[item_id].price * quantity
                for item_id, quantity in quantities.items()
                if not self.items[item_id].deleted
            ),
        )

    def add_to_cart(self, cart_id: int, item_id: int) -> Cart:
        quantities = self.carts[cart_id]
        quantities[item_id] = quantities.get(item_id, 0) + 1
        return self.get_cart(cart_id)
