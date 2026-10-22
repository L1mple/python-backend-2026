from http import HTTPStatus
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from prometheus_fastapi_instrumentator import Instrumentator  

app = FastAPI(title="Shop API")
Instrumentator().instrument(app).expose(app)  

class ItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    price: Annotated[float, Field(ge=0)]


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    price: Annotated[float | None, Field(ge=0)] = None


items: dict[int, dict] = {}

carts: dict[int, dict[int, int]] = {}


next_item_id = 1
next_cart_id = 1


def make_cart_response(cart_id: int) -> dict:
    """
    Convert our internal cart representation

        {item_id: quantity}

    into the representation required by the API.
    """

    cart = carts[cart_id]

    cart_items = []
    total_price = 0.0

    for item_id, quantity in cart.items():
        item = items[item_id]

        available = not item["deleted"]

        cart_items.append(
            {
                "id": item["id"],
                "name": item["name"],
                "quantity": quantity,
                "available": available,
            }
        )

        total_price += item["price"] * quantity

    return {
        "id": cart_id,
        "items": cart_items,
        "price": total_price,
    }


def cart_quantity(cart_id: int) -> int:
    """Total number of item units in a cart."""

    return sum(carts[cart_id].values())


@app.post("/cart", status_code=HTTPStatus.CREATED)
def create_cart(response: Response) -> dict:
    global next_cart_id

    cart_id = next_cart_id
    next_cart_id += 1

    carts[cart_id] = {}

    response.headers["Location"] = f"/cart/{cart_id}"

    return {"id": cart_id}


@app.get("/cart/{cart_id}")
def get_cart(cart_id: int) -> dict:
    if cart_id not in carts:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Cart not found",
        )

    return make_cart_response(cart_id)


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
        cart = make_cart_response(cart_id)
        quantity = cart_quantity(cart_id)

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
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Cart not found",
        )

    if item_id not in items or items[item_id]["deleted"]:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Item not found",
        )

    cart = carts[cart_id]

    if item_id in cart:
        cart[item_id] += 1
    else:
        cart[item_id] = 1

    return make_cart_response(cart_id)


@app.post("/item", status_code=HTTPStatus.CREATED)
def create_item(item: ItemCreate) -> dict:
    global next_item_id

    item_id = next_item_id
    next_item_id += 1

    new_item = {
        "id": item_id,
        "name": item.name,
        "price": item.price,
        "deleted": False,
    }

    items[item_id] = new_item

    return new_item


@app.get("/item/{item_id}")
def get_item(item_id: int) -> dict:
    if item_id not in items or items[item_id]["deleted"]:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Item not found",
        )

    return items[item_id]


@app.get("/item")
def get_items(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    show_deleted: bool = False,
) -> list[dict]:
    result = []

    for item in items.values():
        if not show_deleted and item["deleted"]:
            continue

        if min_price is not None and item["price"] < min_price:
            continue

        if max_price is not None and item["price"] > max_price:
            continue

        result.append(item)

    return result[offset : offset + limit]


@app.put("/item/{item_id}")
def replace_item(item_id: int, item: ItemCreate) -> dict:
    if item_id not in items or items[item_id]["deleted"]:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Item not found",
        )

    new_item = {
        "id": item_id,
        "name": item.name,
        "price": item.price,
        "deleted": False,
    }

    items[item_id] = new_item

    return new_item


@app.patch("/item/{item_id}")
def patch_item(item_id: int, patch: ItemPatch):
    if item_id not in items:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Item not found",
        )

    if items[item_id]["deleted"]:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)

    changes = patch.model_dump(exclude_unset=True)

    for field, value in changes.items():
        items[item_id][field] = value

    return items[item_id]


@app.delete("/item/{item_id}")
def delete_item(item_id: int) -> dict:
    if item_id not in items:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Item not found",
        )

    items[item_id]["deleted"] = True

    return items[item_id]
