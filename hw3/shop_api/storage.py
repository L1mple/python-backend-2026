from itertools import count

from shop_api.schemas import CartItemResponse, CartResponse
from shop_api.structs import Cart, Item
from shop_api import monitoring


class NotFoundError(Exception):
    pass


class ItemDeletedError(Exception):
    pass


_items: dict[int, Item] = {}
_carts: dict[int, Cart] = {}
_item_ids = count(1)
_cart_ids = count(1)

# A snapshot avoids iterating a dictionary while a worker thread adds entries.
monitoring.available_items.set_function(
    lambda: sum(not item.deleted for item in list(_items.values()))
)
monitoring.carts.set_function(lambda: len(_carts))


def create_item(*, name: str, price: float) -> Item:
    item = Item(id=next(_item_ids), name=name, price=price)
    _items[item.id] = item
    monitoring.items_created.inc()
    return item


def get_item(item_id: int, *, include_deleted: bool = False) -> Item:
    item = _items.get(item_id)
    if item is None or (item.deleted and not include_deleted):
        raise NotFoundError(f"Item {item_id} not found")
    return item


def list_items(
        *,
        offset: int = 0,
        limit: int = 10,
        min_price: float | None = None,
        max_price: float | None = None,
        show_deleted: bool = False,
) -> list[Item]:
    ans = []
    min_price_filter = min_price if min_price is not None else float("-inf")
    max_price_filter = max_price if max_price is not None else float("inf")
    for item in _items.values():
        if not show_deleted and item.deleted:
            continue
        if not (min_price_filter <= item.price <= max_price_filter):
            continue
        ans.append(item)
    return ans[offset:offset + limit]


def replace_item(item_id: int, *, name: str, price: float) -> Item:
    try:
        item = get_item(item_id)
    except NotFoundError:
        raise NotFoundError(f"Item {item_id} not found")
    item.name = name
    item.price = price
    return item


def patch_item(item_id: int, *, changes: dict[str, str | float]) -> Item:
    item = get_item(item_id, include_deleted=True)
    if item.deleted:
        raise ItemDeletedError(f"Item {item_id} is deleted")
    if "name" in changes:
        item.name = str(changes["name"])
    if "price" in changes:
        item.price = float(changes["price"])
    return item


def delete_item(item_id: int) -> None:
    item = get_item(item_id, include_deleted=True)
    item.deleted = True


def create_cart() -> Cart:
    cart = Cart(id=next(_cart_ids))
    _carts[cart.id] = cart
    monitoring.carts_created.inc()
    return cart


def get_cart(cart_id: int) -> Cart:
    cart = _carts.get(cart_id)
    if cart is None:
        raise NotFoundError(f"Cart {cart_id} not found")
    return cart


def add_item_to_cart(cart_id: int, item_id: int) -> None:
    cart = get_cart(cart_id)
    item = get_item(item_id)
    if item.id in cart.items:
        cart.items[item.id] += 1
    else:
        cart.items[item.id] = 1
    monitoring.cart_additions.inc()


def build_cart_response(cart: Cart) -> CartResponse:
    price = 0.0
    items_response = []
    for item_id, quantity in cart.items.items():
        item = get_item(item_id, include_deleted=True)
        available = not item.deleted
        if available:
            price += item.price * quantity
        items_response.append(CartItemResponse(
            id=item.id,
            name=item.name,
            quantity=quantity,
            available=available
        ))
    return CartResponse(id=cart.id, items=items_response, price=price)


def list_carts(
        *,
        offset: int = 0,
        limit: int = 10,
        min_price: float | None = None,
        max_price: float | None = None,
        min_quantity: int | None = None,
        max_quantity: int | None = None,
) -> list[CartResponse]:
    ans = []
    min_price_filter = min_price if min_price is not None else float("-inf")
    max_price_filter = max_price if max_price is not None else float("inf")
    min_quantity_filter = min_quantity if min_quantity is not None else float("-inf")
    max_quantity_filter = max_quantity if max_quantity is not None else float("inf")
    for cart in _carts.values():
        cart_response = build_cart_response(cart)
        total_quantity = sum(item.quantity for item in cart_response.items)
        if (not (min_price_filter <= cart_response.price <= max_price_filter) or
                not (min_quantity_filter <= total_quantity <= max_quantity_filter)):
            continue
        ans.append(cart_response)
    return ans[offset:offset + limit]
