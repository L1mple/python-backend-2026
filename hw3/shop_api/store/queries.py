from collections.abc import Iterable

from .models import (
    CartEntity,
    CartItemInfo,
    ItemEntity,
    ItemInfo,
    PatchItemInfo,
)

# ---------- «база данных» ----------

_items: dict[int, ItemEntity] = {}
_carts: dict[int, CartEntity] = {}

_item_id_gen = iter(range(1, 10**9))
_cart_id_gen = iter(range(1, 10**9))


# ---------- items ----------


def create_item(info: ItemInfo) -> ItemEntity:
    item_id = next(_item_id_gen)
    entity = ItemEntity(id=item_id, info=info)
    _items[item_id] = entity
    return entity


def get_item(item_id: int) -> ItemEntity | None:
    """Вернуть товар, если он существует и не удалён."""
    entity = _items.get(item_id)
    if entity is None or entity.deleted:
        return None
    return entity


def get_item_raw(item_id: int) -> ItemEntity | None:
    """Вернуть товар даже если он удалён (нужно для корзины)."""
    return _items.get(item_id)


def get_items(
    offset: int = 0,
    limit: int = 10,
    min_price: float | None = None,
    max_price: float | None = None,
    show_deleted: bool = False,
) -> Iterable[ItemEntity]:
    filtered: list[ItemEntity] = []
    for entity in _items.values():
        if entity.deleted and not show_deleted:
            continue
        if min_price is not None and entity.info.price < min_price:
            continue
        if max_price is not None and entity.info.price > max_price:
            continue
        filtered.append(entity)
    return filtered[offset : offset + limit]


def update_item(item_id: int, info: ItemInfo) -> ItemEntity | None:
    """Полная замена товара (PUT). Не создаёт новый, если не существует."""
    entity = _items.get(item_id)
    if entity is None or entity.deleted:
        return None
    entity.info = info
    return entity


def patch_item(item_id: int, patch: PatchItemInfo) -> ItemEntity | None:
    """Частичное обновление (PATCH). Меняет только не-None поля."""
    entity = _items.get(item_id)
    if entity is None or entity.deleted:
        return None
    if patch.name is not None:
        entity.info.name = patch.name
    if patch.price is not None:
        entity.info.price = patch.price
    return entity


def delete_item(item_id: int) -> ItemEntity | None:
    """Мягкое удаление: помечает товар как deleted, но не удаляет."""
    entity = _items.get(item_id)
    if entity is None:
        return None
    entity.deleted = True
    return entity


# ---------- carts ----------


def create_cart() -> CartEntity:
    cart_id = next(_cart_id_gen)
    entity = CartEntity(id=cart_id)
    _carts[cart_id] = entity
    return entity


def get_cart(cart_id: int) -> CartEntity | None:
    return _carts.get(cart_id)


def _cart_total_price(cart: CartEntity) -> float:
    total = 0.0
    for cart_item in cart.items:
        item = _items.get(cart_item.item_id)
        if item is None:
            continue
        total += item.info.price * cart_item.quantity
    return total


def _cart_total_quantity(cart: CartEntity) -> int:
    return sum(ci.quantity for ci in cart.items)


def get_carts(
    offset: int = 0,
    limit: int = 10,
    min_price: float | None = None,
    max_price: float | None = None,
    min_quantity: int | None = None,
    max_quantity: int | None = None,
) -> Iterable[CartEntity]:
    filtered: list[CartEntity] = []
    for cart in _carts.values():
        price = _cart_total_price(cart)
        quantity = _cart_total_quantity(cart)
        if min_price is not None and price < min_price:
            continue
        if max_price is not None and price > max_price:
            continue
        if min_quantity is not None and quantity < min_quantity:
            continue
        if max_quantity is not None and quantity > max_quantity:
            continue
        filtered.append(cart)
    return filtered[offset : offset + limit]


def add_item_to_cart(cart_id: int, item_id: int) -> CartEntity | None:
    """Добавить товар в корзину. Если уже есть — увеличить quantity."""
    cart = _carts.get(cart_id)
    if cart is None:
        return None
    item = _items.get(item_id)
    if item is None or item.deleted:
        return None

    for cart_item in cart.items:
        if cart_item.item_id == item_id:
            cart_item.quantity += 1
            return cart

    cart.items.append(CartItemInfo(item_id=item_id, quantity=1))
    return cart
