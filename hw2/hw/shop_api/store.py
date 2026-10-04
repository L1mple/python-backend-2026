from itertools import count
from math import fsum

from .models import Cart, CartItem, Item


class Store:
    def __init__(self):
        self.items: dict[int, Item] = {}
        self.carts: dict[int, dict[int, int]] = {}
        self.item_ids = count(1)
        self.cart_ids = count(1)

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
