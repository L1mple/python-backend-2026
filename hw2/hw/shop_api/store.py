from __future__ import annotations

import itertools
from typing import Any

items: dict[int, dict[str, Any]] = {}
carts: dict[int, dict[int, int]] = {}

_item_ids = itertools.count(1)
_cart_ids = itertools.count(1)


# ------------------------- items -------------------------

def create_item(name: str, price: float) -> dict[str, Any]:
    item_id = next(_item_ids)
    item = {"id": item_id, "name": name, "price": price, "deleted": False}
    items[item_id] = item
    return item


def get_item(item_id: int) -> dict[str, Any] | None:
    return items.get(item_id)


def list_items(
    offset: int,
    limit: int,
    min_price: float | None,
    max_price: float | None,
    show_deleted: bool,
) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for item in items.values():
        if not show_deleted and item["deleted"]:
            continue
        if min_price is not None and item["price"] < min_price:
            continue
        if max_price is not None and item["price"] > max_price:
            continue
        found.append(item)
    return found[offset : offset + limit]


def replace_item(item_id: int, name: str, price: float) -> dict[str, Any] | None:
    item = items.get(item_id)
    if item is None:
        return None
    item["name"] = name
    item["price"] = price
    return item


def patch_item(
    item_id: int,
    name: str | None,
    price: float | None,
) -> dict[str, Any] | None:
    item = items.get(item_id)
    if item is None:
        return None
    if name is not None:
        item["name"] = name
    if price is not None:
        item["price"] = price
    return item


def mark_item_deleted(item_id: int) -> bool:
    item = items.get(item_id)
    if item is None:
        return False
    item["deleted"] = True
    return True


# ------------------------- carts -------------------------

def create_cart() -> int:
    cart_id = next(_cart_ids)
    carts[cart_id] = {}
    return cart_id


def get_cart_contents(cart_id: int) -> dict[int, int] | None:
    return carts.get(cart_id)


def add_item_to_cart(cart_id: int, item_id: int) -> None:
    cart = carts[cart_id]
    cart[item_id] = cart.get(item_id, 0) + 1


def cart_price(cart_id: int) -> float:
    return sum(items[i]["price"] * q for i, q in carts[cart_id].items())


def cart_quantity(cart_id: int) -> int:
    return sum(carts[cart_id].values())


def list_carts(
    offset: int,
    limit: int,
    min_price: float | None,
    max_price: float | None,
    min_quantity: int | None,
    max_quantity: int | None,
) -> list[int]:
    found: list[int] = []
    for cart_id in carts:
        if min_price is not None and cart_price(cart_id) < min_price:
            continue
        if max_price is not None and cart_price(cart_id) > max_price:
            continue
        if min_quantity is not None and cart_quantity(cart_id) < min_quantity:
            continue
        if max_quantity is not None and cart_quantity(cart_id) > max_quantity:
            continue
        found.append(cart_id)
    return found[offset : offset + limit]
