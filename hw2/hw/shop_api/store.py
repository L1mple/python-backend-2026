from itertools import count

from .models import (
    Cart,
    CartFilters,
    CartItem,
    Item,
    ItemData,
    ItemFilters,
    ItemPatch,
    ItemReplacement,
)


class Store:
    def __init__(self) -> None:
        self.items: dict[int, Item] = {}
        self.carts: dict[int, dict[int, int]] = {}
        self.item_ids = count(1)
        self.cart_ids = count(1)

    def create_item(self, data: ItemData) -> Item:
        item = Item(id=next(self.item_ids), **data.model_dump())
        self.items[item.id] = item
        return item

    def get_item(self, item_id: int) -> Item | None:
        return self.items.get(item_id)

    def list_items(self, filters: ItemFilters) -> list[Item]:
        items = [
            item
            for item in self.items.values()
            if (filters.show_deleted or not item.deleted)
            and (filters.min_price is None or item.price >= filters.min_price)
            and (filters.max_price is None or item.price <= filters.max_price)
        ]
        return items[filters.offset : filters.offset + filters.limit]

    def replace_item(self, item_id: int, data: ItemReplacement) -> Item:
        item = Item(id=item_id, **data.model_dump())
        self.items[item_id] = item
        return item

    def patch_item(self, item_id: int, data: ItemPatch) -> Item:
        item = self.items[item_id].model_copy(update=data.model_dump(exclude_unset=True))
        self.items[item_id] = item
        return item

    def delete_item(self, item_id: int) -> None:
        self.items[item_id].deleted = True

    def create_cart(self) -> int:
        cart_id = next(self.cart_ids)
        self.carts[cart_id] = {}
        return cart_id

    def get_cart(self, cart_id: int) -> Cart | None:
        if cart_id not in self.carts:
            return None

        items = []
        price = 0.0
        for item_id, quantity in self.carts[cart_id].items():
            item = self.items[item_id]
            items.append(
                CartItem(
                    id=item.id,
                    name=item.name,
                    quantity=quantity,
                    available=not item.deleted,
                )
            )
            if not item.deleted:
                price += item.price * quantity

        return Cart(id=cart_id, items=items, price=price)

    def list_carts(self, filters: CartFilters) -> list[Cart]:
        carts = []
        for cart_id in self.carts:
            cart = self.get_cart(cart_id)
            if cart is None:
                continue
            quantity = sum(item.quantity for item in cart.items)
            if filters.min_price is not None and cart.price < filters.min_price:
                continue
            if filters.max_price is not None and cart.price > filters.max_price:
                continue
            if filters.min_quantity is not None and quantity < filters.min_quantity:
                continue
            if filters.max_quantity is not None and quantity > filters.max_quantity:
                continue
            carts.append(cart)

        return carts[filters.offset : filters.offset + filters.limit]

    def add_item(self, cart_id: int, item_id: int) -> None:
        cart = self.carts[cart_id]
        cart[item_id] = cart.get(item_id, 0) + 1


store = Store()
