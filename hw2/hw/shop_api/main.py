from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Response
from prometheus_fastapi_instrumentator import Instrumentator

from shop_api.schemas import ItemData, ItemPatch


app = FastAPI(title="Shop API")
Instrumentator(excluded_handlers=["/metrics"]).instrument(app).expose(app)

# Пока храним данные в словарях. После остановки сервера они пропадут.
items = {}
carts = {}
next_item_id = 1
next_cart_id = 1


def find_item(item_id: int) -> dict:
    if item_id not in items:
        raise HTTPException(status_code=404, detail="Item not found")
    return items[item_id]


def find_cart(cart_id: int) -> dict:
    if cart_id not in carts:
        raise HTTPException(status_code=404, detail="Cart not found")
    return carts[cart_id]


def cart_to_dict(cart_id: int) -> dict:
    """
    В словаре корзины лежат id товаров и количество каждого товара.
    Название и цену берём из общего словаря items и собираем JSON-ответ.
    """
    cart = find_cart(cart_id)
    result = {"id": cart_id, "items": [], "price": 0.0}
    for item_id in sorted(cart):
        item = items[item_id]
        quantity = cart[item_id]
        result["items"].append({
            "id": item_id,
            "name": item["name"],
            "quantity": quantity,
            "available": not item["deleted"],
        })
        if not item["deleted"]:
            result["price"] += item["price"] * quantity
    return result


@app.post("/item", status_code=201)
async def create_item(data: ItemData) -> dict:
    global next_item_id
    item = {
        "id": next_item_id,
        "name": data.name,
        "price": data.price,
        "deleted": False,
    }
    items[next_item_id] = item
    next_item_id += 1
    return item


@app.get("/item")
async def get_items(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0, allow_inf_nan=False)] = None,
    max_price: Annotated[float | None, Query(ge=0, allow_inf_nan=False)] = None,
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
    return result[offset:offset + limit]


@app.get("/item/{item_id}")
async def get_item(item_id: int) -> dict:
    item = find_item(item_id)
    if item["deleted"]:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.put("/item/{item_id}")
async def replace_item(item_id: int, data: ItemData):
    item = find_item(item_id)
    if item["deleted"]:
        return Response(status_code=304)
    item["name"] = data.name
    item["price"] = data.price
    return item


@app.patch("/item/{item_id}")
async def update_item(item_id: int, data: ItemPatch):
    # Оставляем только переданные клиентом поля, чтобы не стереть остальные.
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes and data.name is None:
        raise HTTPException(status_code=422, detail="Name cannot be null")
    if "price" in changes and data.price is None:
        raise HTTPException(status_code=422, detail="Price cannot be null")

    item = find_item(item_id)
    if item["deleted"]:
        return Response(status_code=304)
    if "name" in changes:
        item["name"] = data.name
    if "price" in changes:
        item["price"] = data.price
    return item


@app.delete("/item/{item_id}")
async def delete_item(item_id: int) -> dict:
    item = find_item(item_id)
    item["deleted"] = True
    return item


@app.post("/cart", status_code=201)
async def create_cart(response: Response) -> dict:
    global next_cart_id
    cart_id = next_cart_id
    carts[cart_id] = {}
    next_cart_id += 1
    response.headers["Location"] = f"/cart/{cart_id}"
    return {"id": cart_id}


@app.get("/cart")
async def get_carts(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0, allow_inf_nan=False)] = None,
    max_price: Annotated[float | None, Query(ge=0, allow_inf_nan=False)] = None,
    min_quantity: Annotated[int | None, Query(ge=0)] = None,
    max_quantity: Annotated[int | None, Query(ge=0)] = None,
) -> list[dict]:
    result = []
    for cart_id in carts:
        data = cart_to_dict(cart_id)
        quantity = 0
        for item in data["items"]:
            quantity += item["quantity"]
        if min_price is not None and data["price"] < min_price:
            continue
        if max_price is not None and data["price"] > max_price:
            continue
        if min_quantity is not None and quantity < min_quantity:
            continue
        if max_quantity is not None and quantity > max_quantity:
            continue
        result.append(data)
    return result[offset:offset + limit]


@app.get("/cart/{cart_id}")
async def get_cart(cart_id: int) -> dict:
    return cart_to_dict(cart_id)


@app.post("/cart/{cart_id}/add/{item_id}")
async def add_item(cart_id: int, item_id: int) -> dict:
    cart = find_cart(cart_id)
    item = find_item(item_id)
    if item["deleted"]:
        raise HTTPException(status_code=404, detail="Item not found")
    if item_id in cart:
        cart[item_id] += 1
    else:
        cart[item_id] = 1
    return cart_to_dict(cart_id)
