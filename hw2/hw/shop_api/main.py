from http import HTTPStatus
from itertools import count
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Response

from .models import Cart, CartCreated, CartItem, Item, ItemData, ItemPatch

app = FastAPI(title="Shop API")


_items: dict[int, Item] = {}
_carts: dict[int, dict[int, int]] = {}
_item_ids = count(1)
_cart_ids = count(1)


def _get_item(item_id: int, *, include_deleted: bool = False) -> Item:
    item = _items.get(item_id)
    if item is None or (item.deleted and not include_deleted):
        raise HTTPException(HTTPStatus.NOT_FOUND, "Item not found")

    return item


def _get_cart_items(cart_id: int) -> dict[int, int]:
    if cart_id not in _carts:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Cart not found")

    return _carts[cart_id]


def _cart_view(cart_id: int) -> Cart:
    positions = []
    price = 0.0
    for item_id, quantity in _get_cart_items(cart_id).items():
        item = _items[item_id]
        positions.append(
            CartItem(
                id=item.id,
                name=item.name,
                quantity=quantity,
                available=not item.deleted,
            )
        )

        if not item.deleted:
            price += item.price * quantity

    return Cart(id=cart_id, items=positions, price=price)


@app.post("/cart", status_code=HTTPStatus.CREATED)
async def create_cart(response: Response) -> CartCreated:
    cart_id = next(_cart_ids)
    _carts[cart_id] = {}
    response.headers["Location"] = f"/cart/{cart_id}"

    return CartCreated(id=cart_id)


@app.get("/cart")
async def list_carts(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0, allow_inf_nan=False)] = None,
    max_price: Annotated[float | None, Query(ge=0, allow_inf_nan=False)] = None,
    min_quantity: Annotated[int | None, Query(ge=0)] = None,
    max_quantity: Annotated[int | None, Query(ge=0)] = None,
) -> list[Cart]:
    result = []
    for cart_id in _carts:
        cart = _cart_view(cart_id)
        quantity = sum(item.quantity for item in cart.items)
        if (
            (min_price is None or cart.price >= min_price)
            and (max_price is None or cart.price <= max_price)
            and (min_quantity is None or quantity >= min_quantity)
            and (max_quantity is None or quantity <= max_quantity)
        ):
            result.append(cart)

    return result[offset : offset + limit]


@app.get("/cart/{cart_id}")
async def get_cart(cart_id: int) -> Cart:
    return _cart_view(cart_id)


@app.post("/cart/{cart_id}/add/{item_id}")
async def add_item_to_cart(cart_id: int, item_id: int) -> Cart:
    cart_items = _get_cart_items(cart_id)
    _get_item(item_id)
    cart_items[item_id] = cart_items.get(item_id, 0) + 1

    return _cart_view(cart_id)


@app.post("/item", status_code=HTTPStatus.CREATED)
async def create_item(data: ItemData, response: Response) -> Item:
    item = Item(id=next(_item_ids), **data.model_dump())
    _items[item.id] = item
    response.headers["Location"] = f"/item/{item.id}"

    return item


@app.get("/item")
async def list_items(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0, allow_inf_nan=False)] = None,
    max_price: Annotated[float | None, Query(ge=0, allow_inf_nan=False)] = None,
    show_deleted: bool = False,
) -> list[Item]:
    result = []
    for item in _items.values():
        if (
            (show_deleted or not item.deleted)
            and (min_price is None or item.price >= min_price)
            and (max_price is None or item.price <= max_price)
        ):
            result.append(item)

    return result[offset : offset + limit]


@app.get("/item/{item_id}")
async def get_item(item_id: int) -> Item:
    return _get_item(item_id)


@app.put("/item/{item_id}")
async def replace_item(item_id: int, data: ItemData) -> Item:
    _get_item(item_id, include_deleted=True)
    item = Item(id=item_id, **data.model_dump())
    _items[item_id] = item

    return item


@app.patch("/item/{item_id}", response_model=Item)
async def patch_item(item_id: int, data: ItemPatch) -> Item | Response:
    item = _get_item(item_id, include_deleted=True)
    if item.deleted:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)

    updated_item = item.model_copy(update=data.model_dump(exclude_unset=True))
    _items[item_id] = updated_item

    return updated_item


@app.delete("/item/{item_id}")
async def delete_item(item_id: int) -> Response:
    item = _get_item(item_id, include_deleted=True)
    item.deleted = True

    return Response(status_code=HTTPStatus.OK)
