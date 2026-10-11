from math import isfinite

from fastapi import HTTPException

from .models import Cart, CartItem, Item, ItemInput, ItemPatch


class Shop:
    """In-memory inventory and carts."""

    def __init__(self):
        self.items: dict[int, Item] = {}
        self.carts: dict[int, dict[int, int]] = {}

    def create_item(self, data: ItemInput) -> Item:
        item = Item(id=len(self.items) + 1, **data.model_dump())
        self.items[item.id] = item
        return item

    def get_item(self, item_id: int, include_deleted: bool = False) -> Item:
        item = self.items.get(item_id)
        if item is None or (item.deleted and not include_deleted):
            raise HTTPException(404, "Item not found")
        return item

    def replace_item(self, item_id: int, data: ItemInput) -> Item:
        self.get_item(item_id, include_deleted=True)
        item = Item(id=item_id, **data.model_dump())
        return self.update_item(item)

    def patch_item(self, item_id: int, data: ItemPatch) -> Item | None:
        item = self.get_item(item_id, include_deleted=True)
        if item.deleted:
            return None
        item = item.model_copy(update=data.model_dump(exclude_unset=True))
        return self.update_item(item)

    def update_item(self, item: Item) -> Item:
        previous = self.items[item.id]
        self.items[item.id] = item
        try:
            for cart_id, quantities in self.carts.items():
                if item.id in quantities:
                    self.get_cart(cart_id)
        except HTTPException:
            self.items[item.id] = previous
            raise
        return item

    def delete_item(self, item_id: int):
        self.get_item(item_id, include_deleted=True).deleted = True

    def create_cart(self) -> int:
        cart_id = len(self.carts) + 1
        self.carts[cart_id] = {}
        return cart_id

    def get_cart(self, cart_id: int) -> Cart:
        quantities = self.carts.get(cart_id)
        if quantities is None:
            raise HTTPException(404, "Cart not found")
        items = [
            CartItem(
                id=item_id,
                name=self.items[item_id].name,
                quantity=quantity,
                available=not self.items[item_id].deleted,
            )
            for item_id, quantity in quantities.items()
        ]
        price = sum(
            self.items[item.id].price * item.quantity
            for item in items
            if item.available
        )
        if not isfinite(price):
            raise HTTPException(422, "Cart total is not finite")
        return Cart(id=cart_id, items=items, price=price)

    def add_item(self, cart_id: int, item_id: int) -> Cart:
        if cart_id not in self.carts:
            raise HTTPException(404, "Cart not found")
        item = self.get_item(item_id)
        if not isfinite(self.get_cart(cart_id).price + item.price):
            raise HTTPException(422, "Cart total is not finite")
        quantities = self.carts[cart_id]
        previous = quantities.get(item_id, 0)
        quantities[item_id] = previous + 1
        try:
            return self.get_cart(cart_id)
        except HTTPException:
            if previous:
                quantities[item_id] = previous
            else:
                quantities.pop(item_id)
            raise
