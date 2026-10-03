from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI(title="Shop API")

items = {}
carts = {}


class ItemCreate(BaseModel):
    name: str
    price: float = Field(ge=0, allow_inf_nan=False)

    model_config = ConfigDict(extra="forbid")


class ItemReplace(ItemCreate):
    deleted: bool = False


class ItemPatch(BaseModel):
    name: str | None = None
    price: float | None = Field(default=None, ge=0, allow_inf_nan=False)

    model_config = ConfigDict(extra="forbid")


def find_item(item_id: int):
    if item_id not in items:
        raise HTTPException(status_code=404, detail="Item not found")
    return items[item_id]


def find_available_item(item_id: int):
    item = find_item(item_id)
    if item["deleted"]:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


def find_cart(cart_id: int):
    if cart_id not in carts:
        raise HTTPException(status_code=404, detail="Cart not found")
    return carts[cart_id]


def make_cart_response(cart_id: int):
    cart = find_cart(cart_id)
    cart_items = []
    total_price = 0.0

    for item_id, quantity in cart.items():
        item = items[item_id]
        available = not item["deleted"]
        cart_items.append({
            "id": item_id,
            "name": item["name"],
            "quantity": quantity,
            "available": available,
        })
        if available:
            total_price += item["price"] * quantity

    return {"id": cart_id, "items": cart_items, "price": total_price}


def count_cart_items(cart):
    quantity = 0
    for item in cart["items"]:
        quantity += item["quantity"]
    return quantity


def in_range(value, minimum, maximum):
    if minimum is not None and value < minimum:
        return False
    if maximum is not None and value > maximum:
        return False
    return True


@app.post("/item", status_code=201)
async def create_item(body: ItemCreate, response: Response):
    item_id = len(items) + 1
    item = {
        "id": item_id,
        "name": body.name,
        "price": body.price,
        "deleted": False,
    }
    items[item_id] = item
    response.headers["Location"] = f"/item/{item_id}"
    return item


@app.get("/item/{item_id}")
async def get_item(item_id: int):
    return find_available_item(item_id)


@app.get("/item")
async def get_items(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, gt=0),
    min_price: float | None = Query(default=None, ge=0, allow_inf_nan=False),
    max_price: float | None = Query(default=None, ge=0, allow_inf_nan=False),
    show_deleted: bool = False,
):
    result = []
    for item in items.values():
        if item["deleted"] and not show_deleted:
            continue
        if not in_range(item["price"], min_price, max_price):
            continue
        result.append(item)
    return result[offset:offset + limit]


@app.put("/item/{item_id}")
async def replace_item(item_id: int, body: ItemReplace):
    find_item(item_id)
    item = {
        "id": item_id,
        "name": body.name,
        "price": body.price,
        "deleted": body.deleted,
    }
    items[item_id] = item
    return item


@app.patch("/item/{item_id}")
async def patch_item(item_id: int, body: ItemPatch):
    if "name" in body.model_fields_set and body.name is None:
        raise HTTPException(status_code=422, detail="Name cannot be null")
    if "price" in body.model_fields_set and body.price is None:
        raise HTTPException(status_code=422, detail="Price cannot be null")

    item = find_item(item_id)
    if item["deleted"]:
        return Response(status_code=304)
    if "name" in body.model_fields_set:
        item["name"] = body.name
    if "price" in body.model_fields_set:
        item["price"] = body.price
    return item


@app.delete("/item/{item_id}")
async def delete_item(item_id: int):
    item = find_item(item_id)
    item["deleted"] = True
    return Response(status_code=200)


@app.post("/cart", status_code=201)
async def create_cart(response: Response):
    cart_id = len(carts) + 1
    carts[cart_id] = {}
    response.headers["Location"] = f"/cart/{cart_id}"
    return {"id": cart_id}


@app.get("/cart/{cart_id}")
async def get_cart(cart_id: int):
    return make_cart_response(cart_id)


@app.get("/cart")
async def get_carts(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, gt=0),
    min_price: float | None = Query(default=None, ge=0, allow_inf_nan=False),
    max_price: float | None = Query(default=None, ge=0, allow_inf_nan=False),
    min_quantity: int | None = Query(default=None, ge=0),
    max_quantity: int | None = Query(default=None, ge=0),
):
    result = []
    for cart_id in carts:
        cart = make_cart_response(cart_id)
        if not in_range(cart["price"], min_price, max_price):
            continue
        quantity = count_cart_items(cart)
        if not in_range(quantity, min_quantity, max_quantity):
            continue
        result.append(cart)
    return result[offset:offset + limit]

@app.post("/cart/{cart_id}/add/{item_id}")
async def add_item_to_cart(cart_id: int, item_id: int):
    cart = find_cart(cart_id)
    find_available_item(item_id)
    if item_id not in cart:
        cart[item_id] = 0

    cart[item_id] += 1
    return make_cart_response(cart_id)
