from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel

app = FastAPI(title="Shop API")
items = {}
carts = {}

class Item(BaseModel):
    name: str
    price: float

def create(cid):
    cart_items = []
    price = 0.0
    for id, qty in carts[cid].items():
        item = items[id]
        cart_items.append({
            "id": id,  "name": item["name"],
            "quantity": qty,
            "available": item["deleted"] == False
        })

        price += item["price"] * qty

    return {
        "id": cid, 
        "items": cart_items, 
        "price": price
            }


@app.post("/cart", status_code=201)
def post_cart(response: Response):
    new_id = len(carts) + 1
    carts[new_id] = {}
    response.headers["location"] = f"/cart/{new_id}"
    return {"id": new_id}

@app.get("/cart/{id}")
def get_cart(id: int):
    return create(id)


@app.get("/cart")
def get_carts(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    min_quantity: int | None = Query(None, ge=0),
    max_quantity: int | None = Query(None, ge=0),
):
    result = []

    for cid in carts:
        cart = create(cid)
        quantity = 0
        for item in cart["items"]:
            quantity += item["quantity"]

        print(cid, cart["price"], quantity)

        if min_price is not None and cart["price"] < min_price:
            continue
        if max_price is not None and cart["price"] > max_price:
            continue

        if min_quantity is not None and quantity < min_quantity:
            continue
        if max_quantity is not None and quantity > max_quantity:
            continue

        result.append(cart)

    return result[offset:offset+limit]


@app.post("/cart/{cart_id}/add/{item_id}")
def add_to_cart(cart_id: int, item_id: int):
    if item_id in carts[cart_id]:
        carts[cart_id][item_id] += 1
    else:
        carts[cart_id][item_id] = 1
    return create(cart_id)

@app.post("/item", status_code=201)
def post_item(body: Item):
    new_id = len(items) + 1
    item = {
        "id": new_id,
        "name": body.name,
        "price": body.price,
        "deleted": False
    }
    items[new_id] = item
    return item

@app.get("/item/{id}")
def get_item(id: int):
    item = items[id]
    if item["deleted"]:
        raise HTTPException(404, "item not found")
    return item


@app.get("/item")
def get_items(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    show_deleted: bool = False,
):
    result = []
    for item in items.values():
        if item["deleted"] == True and show_deleted == False:
            continue
        if min_price is not None and item["price"] < min_price:
            continue
        if max_price is not None and item["price"] > max_price:
            continue

        result.append(item)
    return result[offset:offset + limit]


@app.put("/item/{id}")
def put_item(id: int, body: Item):
    item = items.get(id)
    if item is None:
        raise HTTPException(404, "not found")

    item["name"] = body.name
    item["price"] = body.price
    return item


@app.patch("/item/{id}")
def patch_item(id: int, body: dict):
    item = items[id]

    for key in body.keys():
        if key not in ["name", "price"]:
            raise HTTPException(422, "unknown field")

    if item["deleted"]:
        raise HTTPException(304)

    if "name" in body:
        item["name"] = body["name"]
    if "price" in body:
        item["price"] = body["price"]
    return item


@app.delete("/item/{id}")
def delete_item(id: int):
    items[id]["deleted"] = True
    return items[id]
