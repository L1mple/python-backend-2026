from shop_api.models import CartEntity, CartLine, CartView, ItemEntity


class ShopStore:
    def __init__(self) -> None:
        self._items: dict[int, ItemEntity] = {}
        self._carts: dict[int, CartEntity] = {}
        self._next_item_id = 0
        self._next_cart_id = 0

    def create_cart(self) -> int:
        self._next_cart_id += 1
        cart_id = self._next_cart_id
        self._carts[cart_id] = CartEntity(id=cart_id)

        return cart_id

    def get_cart(self, cart_id: int) -> CartView | None:
        cart = self._carts.get(cart_id)

        if cart is None:
            return None

        return self._view(cart)

    def list_carts(
        self,
        *,
        offset: int,
        limit: int,
        min_price: float | None,
        max_price: float | None,
        min_quantity: int | None,
        max_quantity: int | None,
    ) -> list[CartView]:
        views = [self._view(cart) for cart in self._carts.values()]
        filtered = [
            view
            for view in views
            if _price_matches(view.price, min_price, max_price)
            and _quantity_matches(_total_quantity(view), min_quantity, max_quantity)
        ]

        return filtered[offset : offset + limit]

    def add_to_cart(self, cart_id: int, item_id: int) -> CartView | None:
        cart = self._carts.get(cart_id)
        item = self._items.get(item_id)

        if cart is None or item is None or item.deleted:
            return None

        cart.lines[item_id] = cart.lines.get(item_id, 0) + 1

        return self._view(cart)

    def create_item(self, name: str, price: float) -> ItemEntity:
        self._next_item_id += 1
        item = ItemEntity(id=self._next_item_id, name=name, price=price)
        self._items[item.id] = item

        return item

    def get_item(self, item_id: int, *, include_deleted: bool = False) -> ItemEntity | None:
        item = self._items.get(item_id)

        if item is None:
            return None

        if item.deleted and not include_deleted:
            return None

        return item

    def list_items(
        self,
        *,
        offset: int,
        limit: int,
        min_price: float | None,
        max_price: float | None,
        show_deleted: bool,
    ) -> list[ItemEntity]:
        items = [
            item
            for item in self._items.values()
            if (show_deleted or not item.deleted)
            and _price_matches(item.price, min_price, max_price)
        ]

        return items[offset : offset + limit]

    def replace_item(self, item_id: int, name: str, price: float) -> ItemEntity | None:
        item = self._items.get(item_id)

        if item is None:
            return None

        item.name = name
        item.price = price

        return item

    def patch_item(
        self,
        item_id: int,
        *,
        name: str | None,
        price: float | None,
    ) -> ItemEntity | None:
        item = self._items.get(item_id)

        if item is None or item.deleted:
            return item

        if name is not None:
            item.name = name

        if price is not None:
            item.price = price

        return item

    def delete_item(self, item_id: int) -> ItemEntity | None:
        item = self._items.get(item_id)

        if item is None:
            return None

        item.deleted = True

        return item

    def _view(self, cart: CartEntity) -> CartView:
        lines: list[CartLine] = []
        price = 0.0

        for item_id, quantity in cart.lines.items():
            item = self._items[item_id]
            lines.append(
                CartLine(
                    id=item.id,
                    name=item.name,
                    quantity=quantity,
                    available=not item.deleted,
                )
            )
            price += item.price * quantity

        return CartView(id=cart.id, items=lines, price=price)


def _price_matches(price: float, min_price: float | None, max_price: float | None) -> bool:
    if min_price is not None and price < min_price:
        return False

    if max_price is not None and price > max_price:
        return False

    return True


def _total_quantity(cart: CartView) -> int:
    return sum(line.quantity for line in cart.items)


def _quantity_matches(
    quantity: int,
    min_quantity: int | None,
    max_quantity: int | None,
) -> bool:
    if min_quantity is not None and quantity < min_quantity:
        return False

    if max_quantity is not None and quantity > max_quantity:
        return False

    return True


store = ShopStore()
