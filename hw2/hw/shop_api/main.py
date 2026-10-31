from itertools import count
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict

app = FastAPI(title="Shop API")

item_id_seq = count(1)
cart_id_seq = count(1)

items: dict[int, dict] = {}
carts: dict[int, dict[int, int]] = {}


class ItemCreate(BaseModel):
    name: str
    price: float


class ItemReplace(BaseModel):
    name: str
    price: float


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    price: Optional[float] = None


def get_item_or_404(item_id: int, include_deleted: bool = False) -> dict:
    item = items.get(item_id)
    if item is None or (item["deleted"] and not include_deleted):
        raise HTTPException(status_code=404, detail="Item not found")
    return item


def cart_to_dict(cart_id: int) -> dict:
    cart_items = carts[cart_id]
    result_items = []
    total_price = 0.0

    for item_id, quantity in cart_items.items():
        item = items.get(item_id)
        if item is None:
            continue

        result_items.append(
            {
                "id": item_id,
                "name": item["name"],
                "quantity": quantity,
                "available": not item["deleted"],
            }
        )
        total_price += item["price"] * quantity

    return {
        "id": cart_id,
        "items": result_items,
        "price": total_price,
    }


@app.post("/cart", status_code=201)
def create_cart(response: Response):
    cart_id = next(cart_id_seq)
    carts[cart_id] = {}
    response.headers["Location"] = f"/cart/{cart_id}"
    return {"id": cart_id}


@app.get("/cart/{cart_id}")
def get_cart(cart_id: int):
    if cart_id not in carts:
        raise HTTPException(status_code=404, detail="Cart not found")
    return cart_to_dict(cart_id)


@app.get("/cart")
def get_carts(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    min_quantity: Optional[int] = Query(None, ge=0),
    max_quantity: Optional[int] = Query(None, ge=0),
):
    result = []

    for cart_id in carts:
        cart = cart_to_dict(cart_id)

        if min_price is not None and cart["price"] < min_price:
            continue
        if max_price is not None and cart["price"] > max_price:
            continue

        quantity = sum(item["quantity"] for item in cart["items"])

        if min_quantity is not None and quantity < min_quantity:
            continue
        if max_quantity is not None and quantity > max_quantity:
            continue

        result.append(cart)

    return result[offset : offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}")
def add_item_to_cart(cart_id: int, item_id: int):
    if cart_id not in carts:
        raise HTTPException(status_code=404, detail="Cart not found")

    get_item_or_404(item_id)

    carts[cart_id][item_id] = carts[cart_id].get(item_id, 0) + 1
    return cart_to_dict(cart_id)


@app.post("/item", status_code=201)
def create_item(payload: ItemCreate):
    item_id = next(item_id_seq)
    item = {
        "id": item_id,
        "name": payload.name,
        "price": payload.price,
        "deleted": False,
    }
    items[item_id] = item
    return item


@app.get("/item/{item_id}")
def get_item(item_id: int):
    return get_item_or_404(item_id)


@app.get("/item")
def get_items(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    show_deleted: bool = False,
):
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
def replace_item(item_id: int, payload: ItemReplace):
    item = get_item_or_404(item_id, include_deleted=True)

    item["name"] = payload.name
    item["price"] = payload.price
    return item


@app.patch("/item/{item_id}")
def patch_item(item_id: int, payload: ItemPatch):
    item = get_item_or_404(item_id, include_deleted=True)

    if item["deleted"]:
        return Response(status_code=304)

    data = payload.model_dump(exclude_unset=True)
    item.update(data)
    return item


@app.delete("/item/{item_id}")
def delete_item(item_id: int):
    item = get_item_or_404(item_id, include_deleted=True)
    item["deleted"] = True
    return item
