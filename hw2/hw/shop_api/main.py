from fastapi import FastAPI, Query, HTTPException
from typing import Any, Annotated
from http import HTTPStatus
from fastapi.responses import JSONResponse, Response
from prometheus_client import generate_latest
from shop_api.database import SessionLocal, engine
from shop_api.models import ItemOrm, CartOrm, CartItemOrm, Base
from sqlalchemy import func


Base.metadata.create_all(bind=engine)


app = FastAPI(title="Shop API")
def item_to_dict(item: ItemOrm) -> dict[str, Any]:
    return {
        "id": item.id,
        "name": item.name,
        "price": item.price,
        "deleted": item.deleted,
    }

@app.get("/metrics")
def metrics():
    return Response(
        content=generate_latest(),
        media_type="text/plain",
    )

@app.post("/item")
def create_item(data: dict[str, Any]) -> JSONResponse:
    if "name" not in data or "price" not in data:
        raise HTTPException(
            status_code=422,
            detail="Item must contain name and price",
        )

    with SessionLocal() as session:
        item = ItemOrm(
            name=data["name"],
            price=data["price"],
            deleted=False,
        )

        session.add(item)
        session.commit()
        session.refresh(item)

        return JSONResponse(
            status_code=HTTPStatus.CREATED,
            content=item_to_dict(item),
        )


@app.get("/item/{id}")
def get_item(id: int) -> JSONResponse:
    with SessionLocal() as session:
        item = session.get(ItemOrm, id)
        if item is None or item.deleted:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Item not found",
            )
        return JSONResponse(
            status_code=HTTPStatus.OK,
            content=item_to_dict(item),
        )


@app.get("/item")
def get_items(
    offset: Annotated[int, Query()] = 0,
    limit: Annotated[int, Query()] = 10,
    min_price: Annotated[float | None, Query()] = None,
    max_price: Annotated[float | None, Query()] = None,
    show_deleted: Annotated[bool, Query()] = False,
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

    with SessionLocal() as session:
        query = session.query(ItemOrm)

        if not show_deleted:
            query = query.filter(ItemOrm.deleted == False)
        if min_price is not None:
            query = query.filter(ItemOrm.price >= min_price)
        if max_price is not None:
            query = query.filter(ItemOrm.price <= max_price)

        db_items = (
            query
            .order_by(ItemOrm.id)
            .offset(offset)
            .limit(limit)
            .all()
        )
        result = [item_to_dict(item) for item in db_items]
        return JSONResponse(
            status_code=HTTPStatus.OK,
            content=result,
        )


@app.put("/item/{id}")
def put_item(id: int, data: dict[str, Any]) -> JSONResponse:
    if "name" not in data or "price" not in data:
        raise HTTPException(
            status_code=422,
            detail="Item must contain name and price",
        )

    with SessionLocal() as session:
        item = session.get(ItemOrm, id)
        if item is None or item.deleted:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Item not found",
            )
        item.name = data["name"]
        item.price = data["price"]
        session.commit()
        session.refresh(item)
        return JSONResponse(
            status_code=HTTPStatus.OK,
            content=item_to_dict(item),
        )

@app.patch("/item/{id}")
def patch_item(id: int, data: dict[str, Any]) -> JSONResponse:
    for key in data:
        if key not in ("name", "price"):
            raise HTTPException(
                status_code=422,
                detail="You can change only name and price",
            )
    with SessionLocal() as session:
        item = session.get(ItemOrm, id)
        if item is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Item not found",
            )
        if item.deleted:
            raise HTTPException(
                status_code=HTTPStatus.NOT_MODIFIED,
                detail="Item is deleted",
            )
        if "name" in data:
            item.name = data["name"]
        if "price" in data:
            item.price = data["price"]
        session.commit()
        session.refresh(item)

        return JSONResponse(
            status_code=HTTPStatus.OK,
            content=item_to_dict(item),
        )

@app.delete("/item/{id}")
def delete_item(id: int) -> JSONResponse:
    with SessionLocal() as session:
        item = session.get(ItemOrm, id)
        if item is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Item not found",
            )
        item.deleted = True
        session.commit()
        session.refresh(item)
        return JSONResponse(
            status_code=HTTPStatus.OK,
            content=item_to_dict(item),
        )


@app.post("/cart")
def create_cart() -> JSONResponse:
    with SessionLocal() as session:
        cart = CartOrm()
        session.add(cart)
        session.commit()
        session.refresh(cart)
        return JSONResponse(
            status_code=HTTPStatus.CREATED,
            content={"id": cart.id},
            headers={"location": f"/cart/{cart.id}"},
        )


@app.post("/cart/{cart_id}/add/{item_id}")
def add_item_to_cart(cart_id: int, item_id: int) -> JSONResponse:
    with SessionLocal() as session:
        cart = session.get(CartOrm, cart_id)

        if cart is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Cart not found",
            )
        item = session.get(ItemOrm, item_id)
        if item is None or item.deleted:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Item not found",
            )
        cart_item = (
            session.query(CartItemOrm)
            .filter(
                CartItemOrm.cart_id == cart_id,
                CartItemOrm.item_id == item_id,
            )
            .first()
        )
        if cart_item is None:
            cart_item = CartItemOrm(
                cart_id=cart_id,
                item_id=item_id,
                quantity=1,
            )
            session.add(cart_item)
        else:
            cart_item.quantity += 1
        session.commit()
        return JSONResponse(
            status_code=HTTPStatus.OK,
            content={
                "cart_id": cart_id,
                "item_id": item_id,
            },
        )

@app.get("/cart/{id}")
def get_cart(id: int) -> JSONResponse:
    with SessionLocal() as session:
        cart = session.get(CartOrm, id)
        if cart is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Cart not found",
            )
        rows = (
            session.query(CartItemOrm, ItemOrm)
            .join(
                ItemOrm,
                CartItemOrm.item_id == ItemOrm.id,
            )
            .filter(CartItemOrm.cart_id == id)
            .order_by(CartItemOrm.item_id)
            .all()
        )
        cart_items = []
        total_price = 0.0
        for cart_item, item in rows:
            cart_items.append(
                {
                    "id": item.id,
                    "name": item.name,
                    "quantity": cart_item.quantity,
                    "available": not item.deleted,
                }
            )
            total_price += item.price * cart_item.quantity
        return JSONResponse(
            status_code=HTTPStatus.OK,
            content={
                "id": id,
                "items": cart_items,
                "price": total_price,
            },
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

    with SessionLocal() as session:
        total_price = func.coalesce(
            func.sum(ItemOrm.price * CartItemOrm.quantity),
            0.0,
        )
        total_quantity = func.coalesce(
            func.sum(CartItemOrm.quantity),
            0,
        )
        query = (
            session.query(
                CartOrm.id,
                total_price.label("total_price"),
                total_quantity.label("total_quantity"),
            )
            .outerjoin(
                CartItemOrm,
                CartItemOrm.cart_id == CartOrm.id,
            )
            .outerjoin(
                ItemOrm,
                ItemOrm.id == CartItemOrm.item_id,
            )
            .group_by(CartOrm.id)
        )
        if min_price is not None:
            query = query.having(total_price >= min_price)
        if max_price is not None:
            query = query.having(total_price <= max_price)
        if min_quantity is not None:
            query = query.having(total_quantity >= min_quantity)
        if max_quantity is not None:
            query = query.having(total_quantity <= max_quantity)
        carts_data = (
            query
            .order_by(CartOrm.id)
            .offset(offset)
            .limit(limit)
            .all()
        )

        result = []
        for cart_id, cart_price, _ in carts_data:
            rows = (
                session.query(CartItemOrm, ItemOrm)
                .join(
                    ItemOrm,
                    CartItemOrm.item_id == ItemOrm.id,
                )
                .filter(CartItemOrm.cart_id == cart_id)
                .order_by(CartItemOrm.item_id)
                .all()
            )
            cart_items = [
                {
                    "id": item.id,
                    "name": item.name,
                    "quantity": cart_item.quantity,
                    "available": not item.deleted,
                }
                for cart_item, item in rows
            ]
            result.append(
                {
                    "id": cart_id,
                    "items": cart_items,
                    "price": float(cart_price),
                }
            )
        return JSONResponse(
            status_code=HTTPStatus.OK,
            content=result,
        )
