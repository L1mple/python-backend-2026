from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException, Query, Body, Response, status
from pydantic import BaseModel, ConfigDict

app = FastAPI(title="Shop API")

items: Dict[int, Dict[str, Any]] = {}
carts: Dict[int, Dict[str, Any]] = {}

next_id = 1
next_cart_id = 1

class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Optional[str] = None
    price: Optional[float] = None

def get_item_raw(item_id: int) -> Dict[str, Any]:
    item = items.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

def get_item(item_id: int) -> Dict[str, Any]:
    item = items.get(item_id)
    if item is None or item["deleted"]:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

def get_cart(cart_id: int) -> Dict[str, Any]:
    cart = carts.get(cart_id)
    if cart is None:
        raise HTTPException(status_code=404, detail="Cart not found")
    return cart

def dict_of_cart(cart_id: int) -> Dict[str, Any]:
    cart = get_cart(cart_id)
    out_items = []
    total_price = 0
    for cart_item in cart["items"]:
        item = items.get(cart_item["id"])
        available = not item["deleted"]
        out_items.append({
            "id": item["id"],
            "name": item["name"],
            "quantity": cart_item["quantity"],
            "available": available,
        })
        if available:
            total_price += item["price"] * cart_item["quantity"]
    return {
        "id": cart_id,
        "items": out_items,
        "price": total_price,
    }

def cart_q(cart_id: int) -> int:
    cart = get_cart(cart_id)
    return sum(ci["quantity"] for ci in cart["items"])

@app.post("/cart", status_code=status.HTTP_201_CREATED)
def create_cart(response: Response):
    global next_cart_id
    cart_id = next_cart_id
    next_cart_id += 1
    carts[cart_id] = {
        "id": cart_id,
        "items": [],
    }
    response.headers["Location"] = f"/cart/{cart_id}"
    return {"id": cart_id}

@app.get("/cart/{cart_id}")
def get_cart_e(cart_id: int):
    return dict_of_cart(cart_id)

@app.get("/cart")
def list_carts(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    min_quantity: Optional[int] = Query(None, ge=0),
    max_quantity: Optional[int] = Query(None, ge=0),
):
    result = []
    for cart_id in sorted(carts):
        cart = dict_of_cart(cart_id)
        price = cart["price"]
        quantity = cart_q(cart_id)
        if min_price is not None and price < min_price:
            continue
        if max_price is not None and price > max_price:
            continue
        if min_quantity is not None and quantity < min_quantity:
            continue
        if max_quantity is not None and quantity > max_quantity:
            continue
        result.append(cart)
    return result[offset: offset + limit]

@app.post("/cart/{cart_id}/add/{item_id}")
def add_item_to_cart(cart_id: int, item_id: int):
    cart = get_cart(cart_id)
    get_item(item_id)
    for cart_item in cart["items"]:
        if cart_item["id"] == item_id:
            cart_item["quantity"] += 1
            break
    else:
        cart["items"].append({
            "id": item_id,
            "quantity": 1,
        })

    return dict_of_cart(cart_id)

@app.post("/item", status_code=status.HTTP_201_CREATED)
def create_item(body: Dict[str, Any] = Body(...)):
    global next_id
    price = float(body["price"])
    item_id = next_id
    next_id += 1
    item = {
        "id": item_id,
        "name": body["name"],
        "price": price,
        "deleted": False,
    }
    items[item_id] = item
    return item

@app.get("/item/{item_id}")
def get_item_e(item_id: int):
    return get_item(item_id)

@app.get("/item")
def list_items(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    show_deleted: bool = Query(False),
):
    result = []
    for item_id in sorted(items):
        item = items[item_id]
        if not show_deleted and item["deleted"]:
            continue
        if min_price is not None and item["price"] < min_price:
            continue
        if max_price is not None and item["price"] > max_price:
            continue
        result.append(item)
    return result[offset: offset + limit]

@app.put("/item/{item_id}")
def replace_item(item_id: int, body: Dict[str, Any] = Body(...)):
    get_item(item_id)
    if "name" not in body or "price" not in body:
        raise HTTPException(status_code=422, detail="name and price are required")
    price = float(body["price"])
    item = {
        "id": item_id,
        "name": body["name"],
        "price": price,
        "deleted": False,
    }
    items[item_id] = item
    return item

@app.patch("/item/{item_id}")
def patch_item(item_id: int, body: ItemPatch = Body(...)):
    item = get_item_raw(item_id)
    if item["deleted"]:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED)
    data = body.model_dump(exclude_unset=True)
    if "name" in data:
        item["name"] = data["name"]
    if "price" in data:
        item["price"] = float(data["price"])
    return item

@app.delete("/item/{item_id}")
def delete_item(item_id: int):
    item = get_item_raw(item_id)
    item["deleted"] = True
    return item
