from fastapi import HTTPException, status

from shop_api.contracts import Cart, Item

items: dict[int, Item] = {}
carts: dict[int, dict[int, int]] = {}

next_item_id = 1
next_cart_id = 1

def create_cart_id() -> int:
    global next_cart_id
    cart_id = next_cart_id
    next_cart_id += 1

    return cart_id


def create_item_id() -> int:
    global next_item_id
    item_id = next_item_id
    next_item_id += 1

    return item_id


def get_cart_or_404(cart_id: int) -> dict[int, int]:
    cart = carts.get(cart_id)
    if cart is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart not found",
        )

    return cart


def get_item_or_404(item_id: int) -> Item:
    item = items.get(item_id)
    if item is None or item.deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )

    return item


def build_cart(cart_id: int, cart_data: dict[int, int]) -> Cart:
    cart_items = []
    total_price = 0.0
    for item_id, quantity in cart_data.items():
        item = items.get(item_id)
        if item is None:
            continue

        cart_items.append(
            {
                "id": item.id,
                "name": item.name,
                "quantity": quantity,
                "available": not item.deleted,
            }
        )
        total_price += item.price * quantity

    return Cart(
        id=cart_id,
        items=cart_items,
        price=total_price,
    )