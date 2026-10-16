from http import HTTPStatus
from itertools import count

from fastapi import FastAPI, HTTPException, Response
from pydantic import (
    BaseModel,
    ConfigDict,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveInt,
)

app = FastAPI(title="Shop API")


class ItemCreate(BaseModel):
    name: str
    price: NonNegativeFloat


class ItemPatch(BaseModel):
    name: str | None = None
    price: NonNegativeFloat | None = None

    model_config = ConfigDict(extra="forbid")


Item = dict[str, int | str | float | bool]


items: dict[int, Item] = {}
item_ids = count()
carts: dict[int, dict[int, int]] = {}
cart_ids = count()


@app.post("/item", status_code=HTTPStatus.CREATED)
def create_item(item: ItemCreate, response: Response) -> Item:
    item_id = next(item_ids)
    data: Item = {
        "id": item_id,
        "name": item.name,
        "price": item.price,
        "deleted": False,
    }
    items[item_id] = data
    response.headers["location"] = f"/item/{item_id}"
    return data


@app.post("/cart", status_code=HTTPStatus.CREATED)
def create_cart(response: Response) -> dict[str, int]:
    cart_id = next(cart_ids)
    carts[cart_id] = {}
    response.headers["location"] = f"/cart/{cart_id}"
    return {"id": cart_id}


@app.get("/cart")
def get_carts(
    offset: NonNegativeInt = 0,
    limit: PositiveInt = 10,
    min_price: NonNegativeFloat | None = None,
    max_price: NonNegativeFloat | None = None,
    min_quantity: NonNegativeInt | None = None,
    max_quantity: NonNegativeInt | None = None,
) -> list[dict[str, object]]:
    result = []
    for cart_id, cart in carts.items():
        price = sum(float(items[item_id]["price"]) * quantity for item_id, quantity in cart.items())
        quantity = sum(cart.values())
        if min_price is not None and price < min_price:
            continue
        if max_price is not None and price > max_price:
            continue
        if min_quantity is not None and quantity < min_quantity:
            continue
        if max_quantity is not None and quantity > max_quantity:
            continue
        result.append(cart_data(cart_id))

    return result[offset : offset + limit]


def cart_data(cart_id: int) -> dict[str, object]:
    cart_items = []
    price = 0.0

    for item_id, quantity in carts[cart_id].items():
        item = items[item_id]
        cart_items.append(
            {
                "id": item_id,
                "name": item["name"],
                "quantity": quantity,
                "available": not item["deleted"],
            }
        )
        price += float(item["price"]) * quantity

    return {"id": cart_id, "items": cart_items, "price": price}


@app.post("/cart/{cart_id}/add/{item_id}")
def add_item_to_cart(cart_id: int, item_id: int) -> Response:
    cart = carts.get(cart_id)
    item = items.get(item_id)
    if cart is None or item is None or item["deleted"]:
        raise HTTPException(HTTPStatus.NOT_FOUND)

    cart[item_id] = cart.get(item_id, 0) + 1
    return Response(status_code=HTTPStatus.OK)


@app.get("/cart/{cart_id}")
def get_cart(cart_id: int) -> dict[str, object]:
    if cart_id not in carts:
        raise HTTPException(HTTPStatus.NOT_FOUND)

    return cart_data(cart_id)


@app.get("/item")
def get_items(
    offset: NonNegativeInt = 0,
    limit: PositiveInt = 10,
    min_price: NonNegativeFloat | None = None,
    max_price: NonNegativeFloat | None = None,
    show_deleted: bool = False,
) -> list[Item]:
    result = []
    for item in items.values():
        price = float(item["price"])
        if not show_deleted and item["deleted"]:
            continue
        if min_price is not None and price < min_price:
            continue
        if max_price is not None and price > max_price:
            continue
        result.append(item)

    return result[offset : offset + limit]


@app.get("/item/{item_id}")
def get_item(item_id: int) -> Item:
    item = items.get(item_id)
    if item is None or item["deleted"]:
        raise HTTPException(HTTPStatus.NOT_FOUND)

    return item


@app.put("/item/{item_id}")
def replace_item(item_id: int, update: ItemCreate) -> Item:
    item = items.get(item_id)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND)
    if item["deleted"]:
        raise HTTPException(HTTPStatus.NOT_MODIFIED)

    item.update(name=update.name, price=update.price)
    return item


@app.patch("/item/{item_id}")
def patch_item(item_id: int, update: ItemPatch) -> Item:
    item = items.get(item_id)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND)
    if item["deleted"]:
        raise HTTPException(HTTPStatus.NOT_MODIFIED)

    item.update(update.model_dump(exclude_none=True))
    return item


@app.delete("/item/{item_id}")
def delete_item(item_id: int) -> Response:
    item = items.get(item_id)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND)

    item["deleted"] = True
    return Response(status_code=HTTPStatus.OK)
