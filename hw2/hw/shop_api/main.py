from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import Annotated
from uuid import uuid4

from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel, ConfigDict, Field, model_validator
from shop_api.database import DbSession, get_engine
from shop_api.models import CartLine, CartRow, ItemRow
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Подготовить схему БД до приёма запросов и освободить пул при остановке."""
    engine = await run_in_threadpool(get_engine)
    try:
        yield
    finally:
        await run_in_threadpool(engine.dispose)


app = FastAPI(title="Shop API", lifespan=lifespan)


class ItemInput(BaseModel):
    name: str
    price: float = Field(ge=0)

    model_config = ConfigDict(extra="forbid")


class ItemPatch(BaseModel):
    name: str | None = None
    price: float | None = Field(default=None, ge=0)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def reject_null_fields(self) -> "ItemPatch":
        """Не допускать null для обязательных полей товара."""
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("name and price cannot be null")
        return self


class Item(ItemInput):
    id: int
    deleted: bool = False


class CartItem(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class Cart(BaseModel):
    id: int
    items: list[CartItem]
    price: float


chat_rooms: dict[str, set[WebSocket]] = {}


def cart_view(session: Session, cart_id: int) -> Cart:
    """Собрать корзину по текущему состоянию товаров."""
    if session.get(CartRow, cart_id) is None:
        raise HTTPException(HTTPStatus.NOT_FOUND)
    rows = session.execute(
        select(ItemRow, CartLine.quantity)
        .join(CartLine, CartLine.item_id == ItemRow.id)
        .where(CartLine.cart_id == cart_id)
        .order_by(ItemRow.id)
    ).all()
    cart_items = [
        CartItem(
            id=item.id,
            name=item.name,
            quantity=quantity,
            available=not item.deleted,
        )
        for item, quantity in rows
    ]
    price = sum(item.price * quantity for item, quantity in rows)
    return Cart(id=cart_id, items=cart_items, price=price)


@app.post("/cart", status_code=HTTPStatus.CREATED)
def create_cart(response: Response, session: DbSession) -> dict[str, int]:
    cart = CartRow()
    session.add(cart)
    session.flush()
    response.headers["Location"] = f"/cart/{cart.id}"
    return {"id": cart.id}


@app.get("/cart/{cart_id}")
def get_cart(cart_id: int, session: DbSession) -> Cart:
    return cart_view(session, cart_id)


@app.get("/cart")
def list_carts(
    session: DbSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    min_quantity: Annotated[int | None, Query(ge=0)] = None,
    max_quantity: Annotated[int | None, Query(ge=0)] = None,
) -> list[Cart]:
    totals = (
        select(
            CartLine.cart_id,
            func.sum(ItemRow.price * CartLine.quantity).label("price"),
            func.sum(CartLine.quantity).label("quantity"),
        )
        .join(ItemRow, ItemRow.id == CartLine.item_id)
        .group_by(CartLine.cart_id)
        .subquery()
    )
    query = select(CartRow.id).outerjoin(totals, totals.c.cart_id == CartRow.id)
    for column, lower, upper in (
        (totals.c.price, min_price, max_price),
        (totals.c.quantity, min_quantity, max_quantity),
    ):
        if lower is not None:
            query = query.where(func.coalesce(column, 0) >= lower)
        if upper is not None:
            query = query.where(func.coalesce(column, 0) <= upper)
    cart_ids = session.scalars(query.order_by(CartRow.id).offset(offset).limit(limit))
    return [cart_view(session, cart_id) for cart_id in cart_ids]


@app.post("/cart/{cart_id}/add/{item_id}")
def add_to_cart(cart_id: int, item_id: int, session: DbSession) -> Cart:
    cart = session.scalar(
        select(CartRow).where(CartRow.id == cart_id).with_for_update()
    )
    item = session.get(ItemRow, item_id)
    if cart is None or item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND)
    insert = (
        pg_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
    )
    statement = insert(CartLine).values(cart_id=cart_id, item_id=item_id, quantity=1)
    session.execute(
        statement.on_conflict_do_update(
            index_elements=[CartLine.cart_id, CartLine.item_id],
            set_={"quantity": CartLine.quantity + 1},
        )
    )
    return cart_view(session, cart_id)


@app.post("/item", status_code=HTTPStatus.CREATED)
def create_item(info: ItemInput, response: Response, session: DbSession) -> Item:
    item = ItemRow(**info.model_dump())
    session.add(item)
    session.flush()
    response.headers["Location"] = f"/item/{item.id}"
    return Item.model_validate(item, from_attributes=True)


@app.get("/item/{item_id}")
def get_item(item_id: int, session: DbSession) -> Item:
    item = session.get(ItemRow, item_id)
    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND)
    return Item.model_validate(item, from_attributes=True)


@app.get("/item")
def list_items(
    session: DbSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    show_deleted: bool = False,
) -> list[Item]:
    query = select(ItemRow)
    if not show_deleted:
        query = query.where(ItemRow.deleted.is_(False))
    if min_price is not None:
        query = query.where(ItemRow.price >= min_price)
    if max_price is not None:
        query = query.where(ItemRow.price <= max_price)
    rows = session.scalars(query.order_by(ItemRow.id).offset(offset).limit(limit))
    return [Item.model_validate(item, from_attributes=True) for item in rows]


@app.put("/item/{item_id}")
def replace_item(item_id: int, info: ItemInput, session: DbSession) -> Item:
    item = session.get(ItemRow, item_id)
    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND)
    item.name = info.name
    item.price = info.price
    return Item.model_validate(item, from_attributes=True)


@app.patch("/item/{item_id}", response_model=Item)
def patch_item(item_id: int, info: ItemPatch, session: DbSession) -> Item | Response:
    item = session.get(ItemRow, item_id)
    if item is None or item.deleted:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)
    for field, value in info.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    return Item.model_validate(item, from_attributes=True)


@app.delete("/item/{item_id}")
def delete_item(item_id: int, session: DbSession) -> Response:
    item = session.get(ItemRow, item_id)
    if item is not None:
        item.deleted = True
    return Response(status_code=HTTPStatus.OK)


@app.websocket("/chat/{chat_name}")
async def chat(websocket: WebSocket, chat_name: str) -> None:
    """Пересылать сообщения остальным участникам той же комнаты."""
    username = uuid4().hex[:8]
    await websocket.accept()
    room = chat_rooms.setdefault(chat_name, set())
    room.add(websocket)
    try:
        while True:
            message = await websocket.receive_text()
            for participant in room.copy():
                if participant is not websocket:
                    await participant.send_text(f"{username} :: {message}")
    except WebSocketDisconnect:
        room.remove(websocket)
        if not room:
            del chat_rooms[chat_name]
