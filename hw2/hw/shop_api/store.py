from itertools import count
from math import fsum, isfinite

from .models import Cart, CartItem, Item


class Store:
    def __init__(self):
        self.items: dict[int, Item] = {}
        self.carts: dict[int, dict[int, int]] = {}
        self.item_ids = count(1)
        self.cart_ids = count(1)

    def cart_price(
        self, quantities: dict[int, int], replacement: Item | None = None
    ) -> float:
        prices = []
        for item_id, quantity in quantities.items():
            item = (
                replacement
                if replacement is not None and replacement.id == item_id
                else self.items[item_id]
            )
            if not item.deleted:
                prices.append(item.price * quantity)
        price = fsum(prices)
        if not isfinite(price):
            raise OverflowError("Cart price is too large")
        return price

    def add_to_cart(self, cart_id: int, item_id: int) -> None:
        quantities = self.carts[cart_id].copy()
        quantities[item_id] = quantities.get(item_id, 0) + 1
        self.cart_price(quantities)
        self.carts[cart_id] = quantities

    def update_item(self, item: Item) -> None:
        for quantities in self.carts.values():
            if item.id in quantities:
                self.cart_price(quantities, replacement=item)
        self.items[item.id] = item

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
            price=self.cart_price(quantities),
        )
