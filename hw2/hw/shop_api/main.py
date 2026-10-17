from http import HTTPStatus
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import NonNegativeInt, PositiveInt

from .chat import router as chat_router
from .models import Cart, CartCreated, Item, ItemData, ItemPatch
from .store import Store

app = FastAPI(title="Shop API")
app.include_router(chat_router)
store = Store()

PriceFilter = Annotated[float | None, Query(ge=0, allow_inf_nan=False)]
Offset = Annotated[NonNegativeInt, Query()]
Limit = Annotated[PositiveInt, Query()]
QuantityFilter = Annotated[NonNegativeInt | None, Query()]


def find_item(item_id: int, include_deleted: bool = False) -> Item:
    item = store.items.get(item_id)
    if item is None or (item.deleted and not include_deleted):
        raise HTTPException(HTTPStatus.NOT_FOUND, "Item not found")
    return item


def find_cart(cart_id: int) -> dict[int, int]:
    if cart_id not in store.carts:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Cart not found")
    return store.carts[cart_id]


def save_item(item: Item) -> Item:
    try:
        store.update_item(item)
    except OverflowError as error:
        raise HTTPException(
            HTTPStatus.UNPROCESSABLE_ENTITY, "Cart price is too large"
        ) from error
    return item


@app.post("/cart", status_code=HTTPStatus.CREATED)
async def create_cart(response: Response) -> CartCreated:
    cart_id = next(store.cart_ids)
    store.carts[cart_id] = {}
    response.headers["Location"] = f"/cart/{cart_id}"
    return CartCreated(id=cart_id)


@app.get("/cart/{cart_id}")
async def get_cart(cart_id: int) -> Cart:
    find_cart(cart_id)
    return store.get_cart(cart_id)


@app.get("/cart")
async def list_carts(
    offset: Offset = 0,
    limit: Limit = 10,
    min_price: PriceFilter = None,
    max_price: PriceFilter = None,
    min_quantity: QuantityFilter = None,
    max_quantity: QuantityFilter = None,
) -> list[Cart]:
    carts = []
    for cart_id in store.carts:
        cart = store.get_cart(cart_id)
        quantity = sum(item.quantity for item in cart.items)
        if min_price is not None and cart.price < min_price:
            continue
        if max_price is not None and cart.price > max_price:
            continue
        if min_quantity is not None and quantity < min_quantity:
            continue
        if max_quantity is not None and quantity > max_quantity:
            continue
        carts.append(cart)
    return carts[offset : offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}")
async def add_to_cart(cart_id: int, item_id: int) -> Cart:
    find_cart(cart_id)
    find_item(item_id)
    try:
        store.add_to_cart(cart_id, item_id)
    except OverflowError as error:
        raise HTTPException(
            HTTPStatus.UNPROCESSABLE_ENTITY, "Cart price is too large"
        ) from error
    return store.get_cart(cart_id)


@app.post("/item", status_code=HTTPStatus.CREATED)
async def create_item(data: ItemData, response: Response) -> Item:
    item = Item(id=next(store.item_ids), **data.model_dump())
    store.items[item.id] = item
    response.headers["Location"] = f"/item/{item.id}"
    return item


@app.get("/item/{item_id}")
async def get_item(item_id: int) -> Item:
    return find_item(item_id)


@app.get("/item")
async def list_items(
    offset: Offset = 0,
    limit: Limit = 10,
    min_price: PriceFilter = None,
    max_price: PriceFilter = None,
    show_deleted: bool = False,
) -> list[Item]:
    items = [
        item
        for item in store.items.values()
        if (show_deleted or not item.deleted)
        and (min_price is None or item.price >= min_price)
        and (max_price is None or item.price <= max_price)
    ]
    return items[offset : offset + limit]


@app.put("/item/{item_id}")
async def replace_item(item_id: int, data: ItemData) -> Item:
    find_item(item_id, include_deleted=True)
    item = Item(id=item_id, **data.model_dump())
    return save_item(item)


@app.patch("/item/{item_id}", response_model=Item)
async def patch_item(item_id: int, data: ItemPatch) -> Item | Response:
    item = find_item(item_id, include_deleted=True)
    if item.deleted:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)
    updated = item.model_copy(update=data.model_dump(exclude_unset=True))
    return save_item(updated)


@app.delete("/item/{item_id}")
async def delete_item(item_id: int) -> Response:
    item = find_item(item_id, include_deleted=True)
    item.deleted = True
    return Response(status_code=HTTPStatus.OK)
