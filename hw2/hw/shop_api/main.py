from http import HTTPStatus
from itertools import count
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Response
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, ConfigDict, NonNegativeFloat, NonNegativeInt, PositiveInt

from shop_api.chat import router as chat_router

app = FastAPI(title="Shop API")
app.include_router(chat_router)
Instrumentator().instrument(app).expose(app)


class Item(BaseModel):
    id: int
    name: str
    price: float
    deleted: bool = False


class ItemRequest(BaseModel):
    name: str
    price: NonNegativeFloat


class PatchItemRequest(BaseModel):
    # deleted veya baska alan gelirse 422
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    price: NonNegativeFloat | None = None


class CartItem(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class Cart(BaseModel):
    id: int
    items: list[CartItem]
    price: float


items: dict[int, Item] = {}
item_ids = count(1)

# cart_id -> {item_id: adet}
carts: dict[int, dict[int, int]] = {}
cart_ids = count(1)


def get_item_or_404(item_id: int) -> Item:
    item = items.get(item_id)
    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} not found")
    return item


@app.post("/item", status_code=HTTPStatus.CREATED)
def create_item(body: ItemRequest, response: Response) -> Item:
    item = Item(id=next(item_ids), name=body.name, price=body.price)
    items[item.id] = item
    response.headers["location"] = f"/item/{item.id}"
    return item


@app.get("/item/{item_id}")
def get_item(item_id: int) -> Item:
    return get_item_or_404(item_id)


@app.get("/item")
def get_items(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    show_deleted: bool = False,
) -> list[Item]:
    result = [
        item
        for item in items.values()
        if (show_deleted or not item.deleted)
        and (min_price is None or item.price >= min_price)
        and (max_price is None or item.price <= max_price)
    ]
    return result[offset : offset + limit]


@app.put("/item/{item_id}")
def replace_item(item_id: int, body: ItemRequest) -> Item:
    item = get_item_or_404(item_id)
    item.name = body.name
    item.price = body.price
    return item


@app.patch("/item/{item_id}")
def update_item(item_id: int, body: PatchItemRequest) -> Item:
    item = items.get(item_id)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} not found")
    if item.deleted:
        # 304 body olmadan donmeli
        return Response(status_code=HTTPStatus.NOT_MODIFIED)

    if body.name is not None:
        item.name = body.name
    if body.price is not None:
        item.price = body.price
    return item


@app.delete("/item/{item_id}")
def delete_item(item_id: int) -> Item:
    item = items.get(item_id)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} not found")
    # gercekten silmiyoruz, sadece isaretliyoruz
    item.deleted = True
    return item


def build_cart(cart_id: int) -> Cart:
    cart_items = []
    price = 0.0
    for item_id, quantity in carts[cart_id].items():
        item = items[item_id]
        cart_items.append(
            CartItem(
                id=item.id,
                name=item.name,
                quantity=quantity,
                available=not item.deleted,
            )
        )
        # silinen urun fiyata eklenmesin
        if not item.deleted:
            price += item.price * quantity
    return Cart(id=cart_id, items=cart_items, price=price)


@app.post("/cart", status_code=HTTPStatus.CREATED)
def create_cart(response: Response) -> dict[str, int]:
    cart_id = next(cart_ids)
    carts[cart_id] = {}
    response.headers["location"] = f"/cart/{cart_id}"
    return {"id": cart_id}


@app.get("/cart/{cart_id}")
def get_cart(cart_id: int) -> Cart:
    if cart_id not in carts:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Cart {cart_id} not found")
    return build_cart(cart_id)


@app.get("/cart")
def get_carts(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    min_quantity: Annotated[NonNegativeInt | None, Query()] = None,
    max_quantity: Annotated[NonNegativeInt | None, Query()] = None,
) -> list[Cart]:
    result = []
    for cart_id in carts:
        cart = build_cart(cart_id)
        quantity = sum(item.quantity for item in cart.items)
        if min_price is not None and cart.price < min_price:
            continue
        if max_price is not None and cart.price > max_price:
            continue
        if min_quantity is not None and quantity < min_quantity:
            continue
        if max_quantity is not None and quantity > max_quantity:
            continue
        result.append(cart)
    return result[offset : offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}")
def add_to_cart(cart_id: int, item_id: int) -> Cart:
    if cart_id not in carts:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Cart {cart_id} not found")
    get_item_or_404(item_id)

    cart = carts[cart_id]
    cart[item_id] = cart.get(item_id, 0) + 1
    return build_cart(cart_id)
