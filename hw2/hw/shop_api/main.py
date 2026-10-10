from fastapi import FastAPI, Query, HTTPException
from typing import Any, Annotated
from http import HTTPStatus
from fastapi.responses import JSONResponse, Response
from prometheus_client import generate_latest

app = FastAPI(title="Shop API")
@app.get("/metrics")
def metrics():
    return Response(
        content=generate_latest(),
        media_type="text/plain",
    )

items: dict[int, dict[str, Any]] = {}
next_item_id = 1

carts: dict[int, dict[int, int]] = {}
next_cart_id = 1


@app.post("/item")
def create_item(data: dict[str, Any]) -> JSONResponse:
    global next_item_id

    if "name" not in data or "price" not in data:
        raise HTTPException(
            status_code=422,
            detail="Item must contain name and price",
        )

    item = {
        "id": next_item_id,
        "name": data["name"],
        "price": data["price"],
        "deleted": False,
    }

    items[next_item_id] = item
    next_item_id += 1

    return JSONResponse(
        status_code=HTTPStatus.CREATED,
        content=item,
    )


@app.get("/item/{id}")
def get_item(id: int) -> JSONResponse:
    if id not in items or items[id]["deleted"]:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Item not found",
        )

    return JSONResponse(
        status_code=HTTPStatus.OK,
        content=items[id],
    )


@app.get("/item")
def get_items(
    offset: Annotated[int,Query()] = 0,
    limit: Annotated[int,Query()] = 10,
    min_price: Annotated[float | None, Query()] = None,
    max_price: Annotated[float | None, Query()] = None,
    show_deleted: Annotated[bool, Query()] = False,
) -> JSONResponse:
    if offset < 0:
        raise HTTPException(status_code=422, detail="offset must be non-negative")
    if limit <= 0:
        raise HTTPException(status_code=422, detail="limit must be positive")
    if min_price is not None and min_price < 0:
        raise HTTPException(status_code=422, detail="min_price must be non-negative")
    if max_price is not None and max_price < 0:
        raise HTTPException(status_code=422, detail="max_price must be non-negative")

    result = []
    for item in items.values():
        if not show_deleted and item["deleted"]:
            continue
        if min_price is not None and item["price"] < min_price:
            continue
        if max_price is not None and item["price"] > max_price:
            continue
        result.append(item)

    result = result[offset : offset + limit]
    return JSONResponse(
        status_code=HTTPStatus.OK,
        content=result,
    )


@app.put("/item/{id}")
def put_item(id: int, data: dict[str, Any]) -> JSONResponse:
    if id not in items or items[id]["deleted"]:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Item not found",
        )
    if "name" not in data or "price" not in data:
        raise HTTPException(
            status_code=422,
            detail="Item must contain name and price",
        )
    items[id] = {
        "id": id,
        "name": data["name"],
        "price": data["price"],
        "deleted": False,
    }

    return JSONResponse(
        status_code=HTTPStatus.OK,
        content=items[id],
    )


@app.patch("/item/{id}")
def patch_item(id: int, data: dict[str, Any]) -> JSONResponse:
    if id not in items:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Item not found",
        )
    if items[id]["deleted"]:
        raise HTTPException(
            status_code=304,
            detail="Item is deleted",
        )
    for key in data:
        if key not in ("name", "price"):
            raise HTTPException(
                status_code=422,
                detail="You can change only name and price",
            )
        
    if "name" in data:
        items[id]["name"] = data["name"]
    if "price" in data:
        items[id]["price"] = data["price"]

    return JSONResponse(
        status_code=HTTPStatus.OK,
        content=items[id],
    )

@app.delete("/item/{id}")
def delete_item(id: int) -> JSONResponse:
    if id not in items:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Item not found",
        )

    items[id]["deleted"] = True
    return JSONResponse(
        status_code=HTTPStatus.OK,
        content=items[id],
    )


@app.post("/cart")
def create_cart() -> JSONResponse:
    global next_cart_id
    new_cart_id = next_cart_id
    carts[new_cart_id] = {}
    next_cart_id += 1
    return JSONResponse(
        status_code=HTTPStatus.CREATED,
        content={"id": new_cart_id},
        headers={"location": f"/cart/{new_cart_id}"},
    )


@app.post("/cart/{cart_id}/add/{item_id}")
def add_item_to_cart(cart_id: int, item_id: int) -> JSONResponse:
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
    if item_id in carts[cart_id]:
        carts[cart_id][item_id] += 1
    else:
        carts[cart_id][item_id] = 1

    return JSONResponse(
        status_code=HTTPStatus.OK,
        content={"cart_id": cart_id, "item_id": item_id},
    )

@app.get("/cart/{id}")
def get_cart(id: int) -> JSONResponse:
    if id not in carts:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Cart not found",
        )

    cart_items = []
    total_price = 0
    for item_id, quantity in carts[id].items():
        item = items[item_id]
        cart_items.append(
            {
                "id": item_id,
                "name": item["name"],
                "quantity": quantity,
                "available": not item["deleted"],
            }
        )
        total_price += item["price"] * quantity

    cart = {
        "id": id,
        "items": cart_items,
        "price": total_price,
    }
    return JSONResponse(
        status_code=HTTPStatus.OK,
        content=cart,
    )

@app.get("/cart")
def get_carts(
    offset: Annotated[int, Query()] = 0,
    limit: Annotated[int, Query()] = 10,
    min_price: Annotated[float | None, Query()] = None,
    max_price: Annotated[float | None, Query()] = None,
    min_quantity: Annotated[int | None, Query()] = None,
    max_quantity: Annotated[int | None, Query()] = None,
) -> JSONResponse:
    if offset < 0:
        raise HTTPException(
            status_code=422,
            detail="offset must be non-negative",
        )
    if limit <= 0:
        raise HTTPException(
            status_code=422,
            detail="limit must be positive",
        )
    if min_price is not None and min_price < 0:
        raise HTTPException(
            status_code=422,
            detail="min_price must be non-negative",
        )
    if max_price is not None and max_price < 0:
        raise HTTPException(
            status_code=422,
            detail="max_price must be non-negative",
        )
    if min_quantity is not None and min_quantity < 0:
        raise HTTPException(
            status_code=422,
            detail="min_quantity must be non-negative",
        )
    if max_quantity is not None and max_quantity < 0:
        raise HTTPException(
            status_code=422,
            detail="max_quantity must be non-negative",
        )

    result = []
    for cart_id in carts:
        cart_items = []
        total_price = 0
        total_quantity = 0
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
            total_price += item["price"] * quantity
            total_quantity += quantity

        if min_price is not None and total_price < min_price:
            continue
        if max_price is not None and total_price > max_price:
            continue
        if min_quantity is not None and total_quantity < min_quantity:
            continue
        if max_quantity is not None and total_quantity > max_quantity:
            continue
        result.append(
            {
                "id": cart_id,
                "items": cart_items,
                "price": total_price,
            }
        )

    result = result[offset : offset + limit]
    return JSONResponse(
        status_code=HTTPStatus.OK,
        content=result,
    )