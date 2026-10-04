from typing import Any

from fastapi import FastAPI, Query, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ItemRequest(BaseModel):
    name: str
    price: float = Field(ge=0, allow_inf_nan=False)

    model_config = ConfigDict(extra="forbid")


class PatchItemRequest(BaseModel):
    name: str | None = None
    price: float | None = Field(default=None, ge=0, allow_inf_nan=False)

    model_config = ConfigDict(extra="forbid")

    @field_validator("name", "price")
    @classmethod
    def check_value(cls, value):
        if value is None:
            raise ValueError("Value must not be null")
        return value


app = FastAPI(title="Shop API")

items: dict[int, dict[str, Any]] = {}
carts: dict[int, dict[int, int]] = {}


def get_cart_data(cart_id: int) -> dict[str, Any]:
    """
    Получение содержимого корзины и стоимости доступных товаров
    """

    cart_items = []
    price = 0.0

    for item_id, quantity in carts[cart_id].items():
        item = items[item_id]
        available = not item["deleted"]

        cart_items.append({
            "id": item_id,
            "name": item["name"],
            "quantity": quantity,
            "available": available
        })

        if available:
            price += item["price"] * quantity

    return {"id": cart_id, "items": cart_items, "price": price}


@app.post("/cart", status_code=201)
async def process_post_cart(response: Response) -> dict[str, int]:
    """
    Создание пустой корзины
    """

    cart_id = len(carts) + 1
    carts[cart_id] = {}
    response.headers["location"] = f"/cart/{cart_id}"

    return {"id": cart_id}


@app.get("/cart")
async def process_get_carts(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, gt=0),
    min_price: float | None = Query(default=None, ge=0, allow_inf_nan=False),
    max_price: float | None = Query(default=None, ge=0, allow_inf_nan=False),
    min_quantity: int | None = Query(default=None, ge=0),
    max_quantity: int | None = Query(default=None, ge=0),
) -> list[dict[str, Any]]:
    """
    Получение списка корзин с фильтрацией и пагинацией
    """

    result = []

    for cart_id in carts:
        cart = get_cart_data(cart_id)
        quantity = sum(item["quantity"] for item in cart["items"])

        if min_price is not None and cart["price"] < min_price:
            continue
        if max_price is not None and cart["price"] > max_price:
            continue
        if min_quantity is not None and quantity < min_quantity:
            continue
        if max_quantity is not None and quantity > max_quantity:
            continue

        result.append(cart)

    return result[offset:offset + limit]


@app.get("/cart/{cart_id}")
async def process_get_cart(cart_id: int):
    """
    Получение корзины по идентификатору
    """

    if cart_id not in carts:
        return JSONResponse(status_code=404, content={"error": "Cart not found"})

    return get_cart_data(cart_id)


@app.post("/cart/{cart_id}/add/{item_id}")
async def process_add_item(cart_id: int, item_id: int):
    """
    Добавление одного товара в корзину
    """

    if cart_id not in carts:
        return JSONResponse(status_code=404, content={"error": "Cart not found"})

    if item_id not in items or items[item_id]["deleted"]:
        return JSONResponse(status_code=404, content={"error": "Item not found"})

    cart = carts[cart_id]
    cart[item_id] = cart.get(item_id, 0) + 1

    return get_cart_data(cart_id)


@app.post("/item", status_code=201)
async def process_post_item(info: ItemRequest, response: Response) -> dict[str, Any]:
    """
    Создание товара
    """

    item_id = len(items) + 1
    item = {
        "id": item_id,
        "name": info.name,
        "price": info.price,
        "deleted": False
    }
    items[item_id] = item
    response.headers["location"] = f"/item/{item_id}"

    return item


@app.get("/item")
async def process_get_items(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, gt=0),
    min_price: float | None = Query(default=None, ge=0, allow_inf_nan=False),
    max_price: float | None = Query(default=None, ge=0, allow_inf_nan=False),
    show_deleted: bool = False,
) -> list[dict[str, Any]]:
    """
    Получение списка товаров с фильтрацией и пагинацией
    """

    result = []

    for item in items.values():
        if item["deleted"] and not show_deleted:
            continue
        if min_price is not None and item["price"] < min_price:
            continue
        if max_price is not None and item["price"] > max_price:
            continue

        result.append(item)

    return result[offset:offset + limit]


@app.get("/item/{item_id}")
async def process_get_item(item_id: int):
    """
    Получение товара по идентификатору
    """

    if item_id not in items or items[item_id]["deleted"]:
        return JSONResponse(status_code=404, content={"error": "Item not found"})

    return items[item_id]


@app.put("/item/{item_id}")
async def process_put_item(item_id: int, info: ItemRequest):
    """
    Полное обновление существующего товара
    """

    if item_id not in items:
        return JSONResponse(status_code=404, content={"error": "Item not found"})

    if items[item_id]["deleted"]:
        return Response(status_code=304)

    items[item_id] = {
        "id": item_id,
        "name": info.name,
        "price": info.price,
        "deleted": False
    }

    return items[item_id]


@app.patch("/item/{item_id}")
async def process_patch_item(item_id: int, info: PatchItemRequest):
    """
    Частичное обновление товара
    """

    if item_id not in items:
        return JSONResponse(status_code=404, content={"error": "Item not found"})

    if items[item_id]["deleted"]:
        return Response(status_code=304)

    items[item_id].update(info.model_dump(exclude_unset=True))

    return items[item_id]


@app.delete("/item/{item_id}")
async def process_delete_item(item_id: int) -> dict[str, Any]:
    """
    Пометка товара как удалённого
    """

    if item_id in items:
        items[item_id]["deleted"] = True

    return {}
