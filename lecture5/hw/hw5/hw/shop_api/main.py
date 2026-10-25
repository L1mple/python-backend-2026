from __future__ import annotations

import os
from http import HTTPStatus

from fastapi import FastAPI, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.pool import StaticPool


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite://")
engine_kwargs: dict[str, object] = {}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Item(Base):
    __tablename__ = "items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(500))
    price: Mapped[float] = mapped_column(Float)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cart_items: Mapped[list[CartItem]] = relationship(back_populates="item")


class Cart(Base):
    __tablename__ = "carts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    items: Mapped[list[CartItem]] = relationship(
        back_populates="cart", cascade="all, delete-orphan", order_by="CartItem.item_id"
    )


class CartItem(Base):
    __tablename__ = "cart_items"
    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id"), primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    cart: Mapped[Cart] = relationship(back_populates="items")
    item: Mapped[Item] = relationship(back_populates="cart_items")


Base.metadata.create_all(engine)
app = FastAPI(title="Shop API")
user_ids = 0
chat_clients: dict[str, set[WebSocket]] = {}


def item_response(item: Item) -> dict[str, object]:
    return {"id": item.id, "name": item.name, "price": item.price, "deleted": item.deleted}


def cart_response(cart: Cart) -> dict[str, object]:
    cart_items = [
        {"id": entry.item.id, "name": entry.item.name, "quantity": entry.quantity,
         "available": not entry.item.deleted}
        for entry in cart.items
    ]
    price = sum(entry.item.price * entry.quantity for entry in cart.items if not entry.item.deleted)
    return {"id": cart.id, "items": cart_items, "price": price}


def get_item_or_404(session, item_id: int) -> Item:
    item = session.get(Item, item_id)
    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} was not found")
    return item


def get_cart_or_404(session, cart_id: int) -> Cart:
    cart = session.get(Cart, cart_id)
    if cart is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Cart {cart_id} was not found")
    return cart


async def get_body(request: Request) -> dict[str, object]:
    try:
        body = await request.json()
    except ValueError as error:
        raise HTTPException(HTTPStatus.UNPROCESSABLE_ENTITY, "Request body must be a JSON object") from error
    if not isinstance(body, dict):
        raise HTTPException(HTTPStatus.UNPROCESSABLE_ENTITY, "Request body must be a JSON object")
    return body


def validate_item_body(body: dict[str, object], partial: bool = False) -> tuple[str | None, float | None]:
    if set(body) - {"name", "price"} or (not partial and set(body) != {"name", "price"}):
        raise HTTPException(HTTPStatus.UNPROCESSABLE_ENTITY, "Invalid item data")
    name, price = body.get("name"), body.get("price")
    if not partial or "name" in body:
        if not isinstance(name, str):
            raise HTTPException(HTTPStatus.UNPROCESSABLE_ENTITY, "Item name must be a string")
    if not partial or "price" in body:
        if isinstance(price, bool) or not isinstance(price, (int, float)) or price < 0:
            raise HTTPException(HTTPStatus.UNPROCESSABLE_ENTITY, "Item price must be non-negative")
    return name if isinstance(name, str) else None, float(price) if isinstance(price, (int, float)) else None


@app.post("/cart", status_code=HTTPStatus.CREATED)
async def post_cart(response: Response):
    with SessionLocal() as session:
        cart = Cart()
        session.add(cart)
        session.commit()
        response.headers["location"] = f"/cart/{cart.id}"
        return cart_response(cart)


@app.get("/cart/{cart_id}")
async def get_cart(cart_id: int):
    with SessionLocal() as session:
        return cart_response(get_cart_or_404(session, cart_id))


@app.get("/cart")
async def get_cart_list(
    offset: int = Query(0, ge=0), limit: int = Query(10, gt=0),
    min_price: float | None = Query(None, ge=0), max_price: float | None = Query(None, ge=0),
    min_quantity: int | None = Query(None, ge=0), max_quantity: int | None = Query(None, ge=0),
):
    with SessionLocal() as session:
        result = []
        for cart in session.scalars(select(Cart).order_by(Cart.id)).all():
            data = cart_response(cart)
            quantity = sum(item["quantity"] for item in data["items"])
            if min_price is not None and data["price"] < min_price: continue
            if max_price is not None and data["price"] > max_price: continue
            if min_quantity is not None and quantity < min_quantity: continue
            if max_quantity is not None and quantity > max_quantity: continue
            result.append(data)
        return result[offset:offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}")
async def add_item_to_cart(cart_id: int, item_id: int):
    with SessionLocal() as session:
        cart, item = get_cart_or_404(session, cart_id), get_item_or_404(session, item_id)
        entry = session.get(CartItem, (cart.id, item.id))
        if entry is None:
            cart.items.append(CartItem(item=item, quantity=1))
        else:
            entry.quantity += 1
        session.commit()
        return cart_response(cart)


@app.post("/item", status_code=HTTPStatus.CREATED)
async def post_item(request: Request, response: Response):
    name, price = validate_item_body(await get_body(request))
    with SessionLocal() as session:
        item = Item(name=name or "", price=price or 0.0)
        session.add(item)
        session.commit()
        response.headers["location"] = f"/item/{item.id}"
        return item_response(item)


@app.get("/item/{item_id}")
async def get_item(item_id: int):
    with SessionLocal() as session:
        return item_response(get_item_or_404(session, item_id))


@app.get("/item")
async def get_item_list(
    offset: int = Query(0, ge=0), limit: int = Query(10, gt=0),
    min_price: float | None = Query(None, ge=0), max_price: float | None = Query(None, ge=0),
    show_deleted: bool = Query(False),
):
    with SessionLocal() as session:
        query = select(Item).order_by(Item.id)
        if not show_deleted: query = query.where(Item.deleted.is_(False))
        if min_price is not None: query = query.where(Item.price >= min_price)
        if max_price is not None: query = query.where(Item.price <= max_price)
        return [item_response(i) for i in session.scalars(query.offset(offset).limit(limit)).all()]


@app.put("/item/{item_id}")
async def put_item(item_id: int, request: Request):
    name, price = validate_item_body(await get_body(request))
    with SessionLocal() as session:
        item = session.get(Item, item_id)
        if item is None or item.deleted:
            raise HTTPException(HTTPStatus.NOT_MODIFIED, f"Item {item_id} cannot be replaced")
        item.name, item.price = name or "", price or 0.0
        session.commit()
        return item_response(item)


@app.patch("/item/{item_id}")
async def patch_item(item_id: int, request: Request):
    body = await get_body(request)
    name, price = validate_item_body(body, partial=True)
    with SessionLocal() as session:
        item = session.get(Item, item_id)
        if item is None or item.deleted:
            raise HTTPException(HTTPStatus.NOT_MODIFIED, f"Item {item_id} cannot be updated")
        if "name" in body: item.name = name or ""
        if "price" in body: item.price = price or 0.0
        session.commit()
        return item_response(item)


@app.delete("/item/{item_id}")
async def delete_item(item_id: int):
    with SessionLocal() as session:
        item = session.get(Item, item_id)
        if item is not None and not item.deleted:
            item.deleted = True
            session.commit()
        return Response(status_code=HTTPStatus.OK)


@app.websocket("/chat/{chat_name}")
async def chat(websocket: WebSocket, chat_name: str) -> None:
    global user_ids
    await websocket.accept()
    clients = chat_clients.setdefault(chat_name, set())
    clients.add(websocket)
    user_ids += 1
    username = f"user-{user_ids}"
    try:
        while True:
            message = await websocket.receive_text()
            for client in tuple(clients):
                if client is not websocket:
                    await client.send_text(f"{username} :: {message}")
    except WebSocketDisconnect:
        clients.discard(websocket)
        if not clients:
            chat_clients.pop(chat_name, None)
