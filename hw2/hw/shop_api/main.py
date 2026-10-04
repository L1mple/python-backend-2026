from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel

app = FastAPI(title="Shop API")

items_db = {}
carts_db = {}
item_counter = 0
cart_counter = 0


class ItemCreate(BaseModel):
    name: str
    price: float


class ItemUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None

    model_config = {"extra": "forbid"}


@app.post("/cart", status_code=201)
def create_cart(response: Response):
    global cart_counter
    cart_counter += 1
    cart_id = cart_counter
    carts_db[cart_id] = {"items": {}}
    response.headers["location"] = f"/cart/{cart_id}"
    return {"id": cart_id}


@app.get("/cart/{cart_id}")
def get_cart(cart_id: int):
    if cart_id not in carts_db:
        raise HTTPException(status_code=404, detail="Cart not found")
    
    cart = carts_db[cart_id]
    items = []
    total_price = 0.0
    
    for item_id, quantity in cart["items"].items():
        item = items_db.get(item_id)
        if item and not item["deleted"]:
            items.append({
                "id": item_id,
                "name": item["name"],
                "quantity": quantity,
                "available": True
            })
            total_price += item["price"] * quantity
    
    return {"id": cart_id, "items": items, "price": total_price}


@app.get("/cart")
def get_carts(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    min_quantity: Optional[int] = Query(None, ge=0),
    max_quantity: Optional[int] = Query(None, ge=0)
):
    carts = []
    
    for cart_id in carts_db:
        cart_data = get_cart(cart_id)
        total_quantity = sum(item["quantity"] for item in cart_data["items"])
        total_price = cart_data["price"]
        
        if min_price is not None and total_price < min_price:
            continue
        if max_price is not None and total_price > max_price:
            continue
        if min_quantity is not None and total_quantity < min_quantity:
            continue
        if max_quantity is not None and total_quantity > max_quantity:
            continue
        
        carts.append(cart_data)
    
    return carts[offset:offset+limit]


@app.post("/cart/{cart_id}/add/{item_id}")
def add_to_cart(cart_id: int, item_id: int):
    if cart_id not in carts_db:
        raise HTTPException(status_code=404, detail="Cart not found")
    if item_id not in items_db:
        raise HTTPException(status_code=404, detail="Item not found")
    
    cart = carts_db[cart_id]
    if item_id in cart["items"]:
        cart["items"][item_id] += 1
    else:
        cart["items"][item_id] = 1
    
    return {"status": "ok"}


@app.post("/item", status_code=201)
def create_item(item: ItemCreate):
    global item_counter
    item_counter += 1
    item_id = item_counter
    items_db[item_id] = {
        "id": item_id,
        "name": item.name,
        "price": item.price,
        "deleted": False
    }
    return items_db[item_id]


@app.get("/item/{item_id}")
def get_item(item_id: int):
    if item_id not in items_db or items_db[item_id]["deleted"]:
        raise HTTPException(status_code=404, detail="Item not found")
    
    return items_db[item_id]


@app.get("/item")
def get_items(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    show_deleted: bool = Query(False)
):
    items = []
    
    for item in items_db.values():
        if not show_deleted and item["deleted"]:
            continue
        if min_price is not None and item["price"] < min_price:
            continue
        if max_price is not None and item["price"] > max_price:
            continue
        
        items.append(item)
    
    return items[offset:offset+limit]


@app.put("/item/{item_id}")
def update_item(item_id: int, item: ItemCreate):
    if item_id not in items_db or items_db[item_id]["deleted"]:
        raise HTTPException(status_code=404, detail="Item not found")
    
    items_db[item_id]["name"] = item.name
    items_db[item_id]["price"] = item.price
    
    return items_db[item_id]


@app.patch("/item/{item_id}")
def patch_item(item_id: int, item: ItemUpdate):
    if item_id not in items_db:
        raise HTTPException(status_code=404, detail="Item not found")
    
    if items_db[item_id]["deleted"]:
        return Response(status_code=304)
    
    if item.name is not None:
        items_db[item_id]["name"] = item.name
    if item.price is not None:
        items_db[item_id]["price"] = item.price
    
    return items_db[item_id]


@app.delete("/item/{item_id}")
def delete_item(item_id: int):
    if item_id not in items_db:
        raise HTTPException(status_code=404, detail="Item not found")
    
    items_db[item_id]["deleted"] = True
    
    return {"status": "ok"}