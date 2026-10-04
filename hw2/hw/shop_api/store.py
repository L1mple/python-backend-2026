from dataclasses import dataclass, field


@dataclass(slots=True)
class ItemInfo:
    id: int
    name: str
    price: float
    deleted: bool = False


@dataclass(slots=True)
class CartInfo:
    id: int
    items: dict[int, int] = field(default_factory=dict)  # item_id -> quantity


_items: dict[int, ItemInfo] = {}
_carts: dict[int, CartInfo] = {}
_item_id_counter = 0
_cart_id_counter = 0


def _next_item_id() -> int:
    global _item_id_counter
    _item_id_counter += 1
    return _item_id_counter


def _next_cart_id() -> int:
    global _cart_id_counter
    _cart_id_counter += 1
    return _cart_id_counter


def add_item(name: str, price: float) -> ItemInfo:
    item_id = _next_item_id()
    item = ItemInfo(id=item_id, name=name, price=price)
    _items[item_id] = item
    return item


def get_item(item_id: int) -> ItemInfo | None:
    return _items.get(item_id)


def list_items(
    offset: int = 0,
    limit: int = 10,
    min_price: float | None = None,
    max_price: float | None = None,
    show_deleted: bool = False,
) -> list[ItemInfo]:
    result = []
    for item in _items.values():
        if not show_deleted and item.deleted:
            continue
        if min_price is not None and item.price < min_price:
            continue
        if max_price is not None and item.price > max_price:
            continue
        result.append(item)

    result.sort(key=lambda i: i.id)
    return result[offset : offset + limit]


def replace_item(item_id: int, name: str, price: float) -> ItemInfo | None:
    item = _items.get(item_id)
    if item is None:
        return None
    item.name = name
    item.price = price
    return item


def patch_item(item_id: int, name: str | None, price: float | None) -> ItemInfo | None:
    item = _items.get(item_id)
    if item is None:
        return None
    if name is not None:
        item.name = name
    if price is not None:
        item.price = price
    return item


def delete_item(item_id: int) -> ItemInfo | None:
    item = _items.get(item_id)
    if item is None:
        return None
    item.deleted = True
    return item


def add_cart() -> CartInfo:
    cart_id = _next_cart_id()
    cart = CartInfo(id=cart_id)
    _carts[cart_id] = cart
    return cart


def get_cart(cart_id: int) -> CartInfo | None:
    return _carts.get(cart_id)


def cart_price(cart: CartInfo) -> float:
    total = 0.0
    for item_id, quantity in cart.items.items():
        item = _items.get(item_id)
        if item is not None:
            total += item.price * quantity
    return total


def cart_quantity(cart: CartInfo) -> int:
    return sum(cart.items.values())


def list_carts(
    offset: int = 0,
    limit: int = 10,
    min_price: float | None = None,
    max_price: float | None = None,
    min_quantity: int | None = None,
    max_quantity: int | None = None,
) -> list[CartInfo]:
    result = []
    for cart in _carts.values():
        price = cart_price(cart)
        quantity = cart_quantity(cart)

        if min_price is not None and price < min_price:
            continue
        if max_price is not None and price > max_price:
            continue
        if min_quantity is not None and quantity < min_quantity:
            continue
        if max_quantity is not None and quantity > max_quantity:
            continue

        result.append(cart)

    result.sort(key=lambda c: c.id)
    return result[offset : offset + limit]


def add_item_to_cart(cart_id: int, item_id: int) -> CartInfo | None:
    cart = _carts.get(cart_id)
    if cart is None:
        return None
    if item_id not in _items:
        return None
    cart.items[item_id] = cart.items.get(item_id, 0) + 1
    return cart