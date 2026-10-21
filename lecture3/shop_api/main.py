from http import HTTPStatus
from itertools import count

from fastapi import FastAPI, HTTPException, Query, Response
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, ConfigDict

app = FastAPI(title="Shop API")
Instrumentator().instrument(app).expose(app)

items_db: dict[int, "Item"] = {}
carts_db: dict[int, dict[int, int]] = {}

item_id_seq = count(1)
cart_id_seq = count(1)


class Item(BaseModel):
    id: int
    name: str
    price: float
    deleted: bool = False


class ItemCreate(BaseModel):
    name: str
    price: float


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    price: float | None = None


class CartItem(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class Cart(BaseModel):
    id: int
    items: list[CartItem]
    price: float


def build_cart(cart_id: int) -> Cart:
    cart_items = []
    price = 0.0

    for item_id, quantity in carts_db[cart_id].items():
        item = items_db[item_id]
        price += item.price * quantity
        cart_items.append(
            CartItem(
                id=item.id,
                name=item.name,
                quantity=quantity,
                available=not item.deleted,
            )
        )

    return Cart(id=cart_id, items=cart_items, price=price)


@app.post("/cart", status_code=HTTPStatus.CREATED)
def create_cart(response: Response):
    cart_id = next(cart_id_seq)
    carts_db[cart_id] = {}
    response.headers["location"] = f"/cart/{cart_id}"
    return {"id": cart_id}


@app.get("/cart/{cart_id}")
def get_cart(cart_id: int) -> Cart:
    if cart_id not in carts_db:
        raise HTTPException(HTTPStatus.NOT_FOUND)

    return build_cart(cart_id)


@app.get("/cart")
def get_cart_list(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    min_quantity: int | None = Query(None, ge=0),
    max_quantity: int | None = Query(None, ge=0),
) -> list[Cart]:
    carts = [build_cart(cart_id) for cart_id in carts_db]

    if min_price is not None:
        carts = [c for c in carts if c.price >= min_price]
    if max_price is not None:
        carts = [c for c in carts if c.price <= max_price]

    if min_quantity is not None:
        carts = [c for c in carts if sum(i.quantity for i in c.items) >= min_quantity]
    if max_quantity is not None:
        carts = [c for c in carts if sum(i.quantity for i in c.items) <= max_quantity]

    return carts[offset : offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}")
def add_item_to_cart(cart_id: int, item_id: int) -> Cart:
    if cart_id not in carts_db or item_id not in items_db:
        raise HTTPException(HTTPStatus.NOT_FOUND)

    cart = carts_db[cart_id]
    cart[item_id] = cart.get(item_id, 0) + 1

    return build_cart(cart_id)


@app.post("/item", status_code=HTTPStatus.CREATED)
def create_item(body: ItemCreate) -> Item:
    item_id = next(item_id_seq)
    item = Item(id=item_id, name=body.name, price=body.price)
    items_db[item_id] = item

    return item


@app.get("/item/{item_id}")
def get_item(item_id: int) -> Item:
    item = items_db.get(item_id)

    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND)

    return item


@app.get("/item")
def get_item_list(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    show_deleted: bool = False,
) -> list[Item]:
    items = list(items_db.values())

    if not show_deleted:
        items = [i for i in items if not i.deleted]

    if min_price is not None:
        items = [i for i in items if i.price >= min_price]
    if max_price is not None:
        items = [i for i in items if i.price <= max_price]

    return items[offset : offset + limit]


@app.put("/item/{item_id}")
def put_item(item_id: int, body: ItemCreate) -> Item:
    if item_id not in items_db:
        raise HTTPException(HTTPStatus.NOT_FOUND)

    item = items_db[item_id]
    item.name = body.name
    item.price = body.price

    return item


@app.patch("/item/{item_id}")
def patch_item(item_id: int, body: ItemPatch):
    if item_id not in items_db:
        raise HTTPException(HTTPStatus.NOT_FOUND)

    item = items_db[item_id]

    if item.deleted:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(item, field, value)

    return item


@app.delete("/item/{item_id}")
def delete_item(item_id: int):
    item = items_db.get(item_id)

    if item is not None:
        item.deleted = True

    return {"id": item_id, "deleted": True}
