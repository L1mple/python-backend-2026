from fastapi import FastAPI, HTTPException, Query, Response

from http import HTTPStatus
from typing import Annotated
from pydantic import NonNegativeInt, PositiveInt

from shop_api.models import (
    CartCreatedResponse,
    CartItemResponse,
    CartResponse,
    ItemCreate,
    ItemPatch,
    ItemPut,
    ItemResponse
)

app = FastAPI(title="Shop API")

_items: dict[int, ItemResponse] = {}
_carts: dict[int, dict[int, int]] = {}
_item_id_gen = iter(range(1, 10**9))
_cart_id_gen = iter(range(1, 10**9))

def _build_cart(cart_id: int) -> CartResponse:
    items: list[CartItemResponse] = []
    total = 0.0

    for item_id, quantity in _carts[cart_id].items():
        item = _items.get(item_id)
        if item is None:
            continue
        available = not item.deleted
        items.append(
            CartItemResponse(
                id=item.id,
                name=item.name,
                quantity=quantity,
                available=available,
            )
        )
        if available:
            total += item.price * quantity
    return CartResponse(id=cart_id, items=items, price=total)

@app.post("/cart", status_code=HTTPStatus.CREATED, response_model=CartCreatedResponse)
async def create_cart(response: Response) -> CartCreatedResponse:
    cart_id = next(_cart_id_gen)
    _carts[cart_id] = {}
    response.headers["location"] = f"/cart/{cart_id}"
    return CartCreatedResponse(id=cart_id)

@app.get("/cart/{cart_id}", response_model=CartResponse)
async def get_cart(cart_id: int) -> CartResponse:
    if cart_id not in _carts:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Cart not found")
    return _build_cart(cart_id)

@app.get("/cart", response_model=list[CartResponse])
async def get_carts(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    min_quantity: Annotated[NonNegativeInt | None, Query()] = None,
    max_quantity: Annotated[NonNegativeInt | None, Query()] = None,
) -> list[CartResponse]:
    carts = [_build_cart(cid) for cid in _carts]

    if min_price is not None:
        carts = [c for c in carts if c.price >= min_price]
    if max_price is not None:
        carts = [c for c in carts if c.price <= max_price]
    if min_quantity is not None:
        carts = [c for c in carts if sum(i.quantity for i in c.items) >= min_quantity]
    if max_quantity is not None:
        carts = [c for c in carts if sum(i.quantity for i in c.items) <= max_quantity]
    return carts[offset : offset + limit]

@app.post("/cart/{cart_id}/add/{item_id}", response_model=CartResponse)
async def add_item_to_cart(cart_id: int, item_id: int) -> CartResponse:
    if cart_id not in _carts:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Cart not found")
    item = _items.get(item_id)
    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Item not found")
    cart = _carts[cart_id]
    cart[item_id] = cart.get(item_id, 0) + 1
    return _build_cart(cart_id)

@app.post("/item", status_code=HTTPStatus.CREATED, response_model=ItemResponse)
async def create_item(body: ItemCreate, response: Response) -> ItemResponse:
    item_id = next(_item_id_gen)
    item = ItemResponse(id=item_id, name=body.name, price=body.price, deleted=False)
    _items[item_id] = item
    response.headers["location"] = f"/item/{item_id}"
    return item

@app.get("/item/{item_id}", response_model=ItemResponse)
async def get_item(item_id: int) -> ItemResponse:
    item = _items.get(item_id)
    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Item not found")
    return item

@app.get("/item", response_model=list[ItemResponse])
async def get_items(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    show_deleted: bool = False,
) -> list[ItemResponse]:
    items = list(_items.values())
    if not show_deleted:
        items = [i for i in items if not i.deleted]
    if min_price is not None:
        items = [i for i in items if i.price >= min_price]
    if max_price is not None:
        items = [i for i in items if i.price <= max_price]
    return items[offset : offset + limit]

@app.put("/item/{item_id}", response_model=ItemResponse)
async def put_item(item_id: int, body: ItemPut) -> ItemResponse:
    item = _items.get(item_id)
    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Item not found")
    item.name = body.name
    item.price = body.price
    return item

@app.patch("/item/{item_id}", response_model=ItemResponse)
async def patch_item(item_id: int, body: ItemPatch) -> ItemResponse:
    item = _items.get(item_id)
    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_MODIFIED, "Item not found")

    if body.name is not None:
        item.name = body.name
    if body.price is not None:
        item.price = body.price
    return item

@app.delete("/item/{item_id}")
async def delete_item(item_id: int) -> dict:
    item = _items.get(item_id)
    if item is not None:
        item.deleted = True
    return {}