from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .chat import router as chat_router
from .database import CartItemRow, CartRow, ItemRow, get_engine, get_session
from .models import Cart, CartFilters, CartItem, Item, ItemData, ItemFilters, ItemPatch

@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_in_threadpool(get_engine)
    yield


app = FastAPI(title="Shop API", lifespan=lifespan)
app.include_router(chat_router)
DB = Annotated[Session, Depends(get_session)]


def item_response(row: ItemRow) -> Item:
    return Item(id=row.id, name=row.name, price=row.price, deleted=row.deleted)


def find_item(db: Session, item_id: int, *, lock: bool = False) -> ItemRow:
    query = select(ItemRow).where(ItemRow.id == item_id)
    if lock:
        query = query.with_for_update()
    item = db.scalar(query)
    if item is None or item.deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    return item


def find_cart(db: Session, cart_id: int, *, lock: bool = False) -> CartRow:
    query = select(CartRow).where(CartRow.id == cart_id)
    if lock:
        query = query.with_for_update()
    cart = db.scalar(query)
    if cart is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cart not found")
    return cart


def build_carts(db: Session, cart_ids: list[int]) -> list[Cart]:
    carts = {cart_id: Cart(id=cart_id, items=[], price=0.0) for cart_id in cart_ids}
    if not carts:
        return []
    rows = db.execute(
        select(CartItemRow, ItemRow)
        .join(ItemRow, CartItemRow.item_id == ItemRow.id)
        .where(CartItemRow.cart_id.in_(cart_ids))
        .order_by(CartItemRow.cart_id, CartItemRow.item_id)
    )
    for entry, item in rows:
        cart = carts[entry.cart_id]
        cart.items.append(CartItem(
            id=item.id, name=item.name, quantity=entry.quantity, available=not item.deleted,
        ))
        if not item.deleted:
            cart.price += item.price * entry.quantity
    return list(carts.values())


@app.post("/item", status_code=status.HTTP_201_CREATED)
def create_item(data: ItemData, response: Response, db: DB) -> Item:
    with db.begin():
        item = ItemRow(**data.model_dump())
        db.add(item)
        db.flush()
        result = item_response(item)
    response.headers["Location"] = f"/item/{result.id}"
    return result


@app.get("/item")
def list_items(filters: Annotated[ItemFilters, Query()], db: DB) -> list[Item]:
    query = select(ItemRow)
    if not filters.show_deleted:
        query = query.where(ItemRow.deleted.is_(False))
    if filters.min_price is not None:
        query = query.where(ItemRow.price >= filters.min_price)
    if filters.max_price is not None:
        query = query.where(ItemRow.price <= filters.max_price)
    query = query.order_by(ItemRow.id).offset(filters.offset).limit(filters.limit)
    return [item_response(item) for item in db.scalars(query)]


@app.get("/item/{item_id}")
def get_item(item_id: int, db: DB) -> Item:
    return item_response(find_item(db, item_id))


@app.put("/item/{item_id}")
def replace_item(item_id: int, data: ItemData, db: DB) -> Item:
    with db.begin():
        item = find_item(db, item_id, lock=True)
        for field, value in data.model_dump().items():
            setattr(item, field, value)
        result = item_response(item)
    return result


@app.patch("/item/{item_id}", response_model=Item)
def patch_item(item_id: int, data: ItemPatch, db: DB) -> Item | Response:
    with db.begin():
        item = db.scalar(select(ItemRow).where(ItemRow.id == item_id).with_for_update())
        if item is None or item.deleted:
            return Response(status_code=status.HTTP_304_NOT_MODIFIED)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        result = item_response(item)
    return result


@app.delete("/item/{item_id}")
def delete_item(item_id: int, db: DB) -> Response:
    with db.begin():
        item = db.scalar(select(ItemRow).where(ItemRow.id == item_id).with_for_update())
        if item is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
        item.deleted = True
    return Response(status_code=status.HTTP_200_OK)


@app.post("/cart", status_code=status.HTTP_201_CREATED)
def create_cart(response: Response, db: DB) -> dict[str, int]:
    with db.begin():
        cart = CartRow()
        db.add(cart)
        db.flush()
        cart_id = cart.id
    response.headers["Location"] = f"/cart/{cart_id}"
    return {"id": cart_id}


@app.get("/cart")
def list_carts(filters: Annotated[CartFilters, Query()], db: DB) -> list[Cart]:
    totals = (
        select(
            CartItemRow.cart_id,
            func.sum(CartItemRow.quantity).label("quantity"),
            func.sum(case(
                (ItemRow.deleted.is_(False), ItemRow.price * CartItemRow.quantity), else_=0,
            )).label("price"),
        )
        .join(ItemRow, ItemRow.id == CartItemRow.item_id)
        .group_by(CartItemRow.cart_id)
        .subquery()
    )
    query = select(CartRow.id).outerjoin(totals, CartRow.id == totals.c.cart_id)
    for column, minimum, maximum in [
        (totals.c.price, filters.min_price, filters.max_price),
        (totals.c.quantity, filters.min_quantity, filters.max_quantity),
    ]:
        value = func.coalesce(column, 0)
        if minimum is not None:
            query = query.where(value >= minimum)
        if maximum is not None:
            query = query.where(value <= maximum)
    query = query.order_by(CartRow.id).offset(filters.offset).limit(filters.limit)
    return build_carts(db, list(db.scalars(query)))


@app.get("/cart/{cart_id}")
def get_cart(cart_id: int, db: DB) -> Cart:
    find_cart(db, cart_id)
    return build_carts(db, [cart_id])[0]


@app.post("/cart/{cart_id}/add/{item_id}")
def add_to_cart(cart_id: int, item_id: int, db: DB) -> Cart:
    with db.begin():
        # All writers lock the cart first, so concurrent increments cannot get lost.
        find_cart(db, cart_id, lock=True)
        find_item(db, item_id, lock=True)
        entry = db.get(CartItemRow, (cart_id, item_id))
        if entry is None:
            db.add(CartItemRow(cart_id=cart_id, item_id=item_id, quantity=1))
        else:
            entry.quantity += 1
        db.flush()
        result = build_carts(db, [cart_id])[0]
    return result
