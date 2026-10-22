from http import HTTPStatus
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI(title="Shop API")


class ItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    price: float = Field(ge=0)


class ItemReplace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    price: float = Field(ge=0)


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    price: float | None = Field(default=None, ge=0)


items: dict[int, dict] = {}
carts: dict[int, dict[int, int]] = {}

next_item_id = 1
next_cart_id = 1


def item_view(item_id: int) -> dict:
    item = items[item_id]

    return {
        "id": item_id,
        "name": item["name"],
        "price": item["price"],
        "deleted": item["deleted"],
    }


def cart_view(cart_id: int) -> dict:
    cart = carts[cart_id]

    cart_items = []
    total_price = 0.0

    for item_id, quantity in cart.items():
        item = items[item_id]

        available = not item["deleted"]

        cart_items.append(
            {
                "id": item_id,
                "name": item["name"],
                "quantity": quantity,
                "available": available,
            }
        )

        if available:
            total_price += item["price"] * quantity

    return {
        "id": cart_id,
        "items": cart_items,
        "price": total_price,
    }


@app.post("/cart", status_code=HTTPStatus.CREATED)
def create_cart(response: Response) -> dict[str, int]:
    global next_cart_id

    cart_id = next_cart_id
    next_cart_id += 1

    carts[cart_id] = {}

    response.headers["Location"] = f"/cart/{cart_id}"

    return {"id": cart_id}


@app.get("/cart/{cart_id}")
def get_cart(cart_id: int) -> dict:
    if cart_id not in carts:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)

    return cart_view(cart_id)


@app.get("/cart")
def get_carts(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    min_quantity: Annotated[int | None, Query(ge=0)] = None,
    max_quantity: Annotated[int | None, Query(ge=0)] = None,
) -> list[dict]:
    result = []

    for cart_id in carts:
        cart = cart_view(cart_id)

        quantity = sum(
            item["quantity"]
            for item in cart["items"]
        )

        if min_price is not None and cart["price"] < min_price:
            continue

        if max_price is not None and cart["price"] > max_price:
            continue

        if min_quantity is not None and quantity < min_quantity:
            continue

        if max_quantity is not None and quantity > max_quantity:
            continue

        result.append(cart)

    return result[offset : offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}")
def add_item_to_cart(cart_id: int, item_id: int) -> dict:
    if cart_id not in carts:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)

    if item_id not in items or items[item_id]["deleted"]:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)

    cart = carts[cart_id]

    cart[item_id] = cart.get(item_id, 0) + 1

    return cart_view(cart_id)


@app.post("/item", status_code=HTTPStatus.CREATED)
def create_item(body: ItemCreate, response: Response) -> dict:
    global next_item_id

    item_id = next_item_id
    next_item_id += 1

    items[item_id] = {
        "name": body.name,
        "price": body.price,
        "deleted": False,
    }

    response.headers["Location"] = f"/item/{item_id}"

    return item_view(item_id)


@app.get("/item/{item_id}")
def get_item(item_id: int) -> dict:
    if item_id not in items or items[item_id]["deleted"]:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)

    return item_view(item_id)


@app.get("/item")
def get_items(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    show_deleted: bool = False,
) -> list[dict]:
    result = []

    for item_id, item in items.items():
        if item["deleted"] and not show_deleted:
            continue

        if min_price is not None and item["price"] < min_price:
            continue

        if max_price is not None and item["price"] > max_price:
            continue

        result.append(item_view(item_id))

    return result[offset : offset + limit]


@app.put("/item/{item_id}")
def replace_item(item_id: int, body: ItemReplace):
    if item_id not in items:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)

    if items[item_id]["deleted"]:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)

    items[item_id] = {
        "name": body.name,
        "price": body.price,
        "deleted": False,
    }

    return item_view(item_id)


@app.patch("/item/{item_id}")
def patch_item(item_id: int, body: ItemPatch):
    if item_id not in items:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)

    if items[item_id]["deleted"]:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)

    changes = body.model_dump(exclude_unset=True)

    items[item_id].update(changes)

    return item_view(item_id)


@app.delete("/item/{item_id}")
def delete_item(item_id: int) -> dict:
    if item_id not in items:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)

    items[item_id]["deleted"] = True

    return item_view(item_id)