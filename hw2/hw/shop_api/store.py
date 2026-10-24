from itertools import islice
from math import isfinite

from .errors import CartTotalOverflowError, ResourceNotFoundError
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
            raise ResourceNotFoundError("Item not found")
        return item

    def list_items(self, offset, limit, min_price, max_price, show_deleted):
        items = (
            item
            for item in self.items.values()
            if (show_deleted or not item.deleted)
            and (min_price is None or item.price >= min_price)
            and (max_price is None or item.price <= max_price)
        )
        # Bound islice indices without restricting API integers.
        size = len(self.items)
        return list(islice(items, min(offset, size), min(offset + limit, size)))

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
            for quantities in self.carts.values():
                if item.id in quantities:
                    self._cart_price(quantities)
        except CartTotalOverflowError:
            self.items[item.id] = previous
            raise
        return item

    def delete_item(self, item_id: int):
        self.get_item(item_id, include_deleted=True).deleted = True

    def create_cart(self) -> int:
        cart_id = len(self.carts) + 1
        self.carts[cart_id] = {}
        return cart_id

    def _cart_price(self, quantities: dict[int, int]) -> float:
        price = sum(
            self.items[item_id].price * quantity
            for item_id, quantity in quantities.items()
            if not self.items[item_id].deleted
        )
        if not isfinite(price):
            raise CartTotalOverflowError("Cart total is not finite")
        return price

    def get_cart(self, cart_id: int) -> Cart:
        quantities = self.carts.get(cart_id)
        if quantities is None:
            raise ResourceNotFoundError("Cart not found")
        price = self._cart_price(quantities)
        items = [
            CartItem(
                id=item_id,
                name=self.items[item_id].name,
                quantity=quantity,
                available=not self.items[item_id].deleted,
            )
            for item_id, quantity in quantities.items()
        ]
        return Cart(id=cart_id, items=items, price=price)

    def list_carts(
        self, offset, limit, min_price, max_price, min_quantity, max_quantity
    ):
        def matching_ids():
            for cart_id, quantities in self.carts.items():
                price = self._cart_price(quantities)
                quantity = sum(quantities.values())
                if min_price is not None and price < min_price:
                    continue
                if max_price is not None and price > max_price:
                    continue
                if min_quantity is not None and quantity < min_quantity:
                    continue
                if max_quantity is not None and quantity > max_quantity:
                    continue
                yield cart_id

        size = len(self.carts)
        page = islice(matching_ids(), min(offset, size), min(offset + limit, size))
        return [self.get_cart(cart_id) for cart_id in page]

    def add_item(self, cart_id: int, item_id: int) -> Cart:
        if cart_id not in self.carts:
            raise ResourceNotFoundError("Cart not found")
        item = self.get_item(item_id)
        if not isfinite(self.get_cart(cart_id).price + item.price):
            raise CartTotalOverflowError("Cart total is not finite")
        quantities = self.carts[cart_id]
        previous = quantities.get(item_id, 0)
        quantities[item_id] = previous + 1
        try:
            return self.get_cart(cart_id)
        except CartTotalOverflowError:
            if previous:
                quantities[item_id] = previous
            else:
                quantities.pop(item_id)
            raise
