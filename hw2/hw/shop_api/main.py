import random
from collections import defaultdict
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from .db import CartItemOrm, CartOrm, ItemOrm, get_session, init_db

app = FastAPI(title="Shop API")

# hw3: экспортирует /metrics для Prometheus
Instrumentator().instrument(app).expose(app)

# hw4: таблицы создаются сразу при импорте модуля (а не в on_event("startup")),
# чтобы это гарантированно работало и под TestClient в тестах.
init_db()


# --------------------------------------------------------------------------
# Модели
# --------------------------------------------------------------------------


class Item(BaseModel):
    id: int
    name: str
    price: float
    deleted: bool = False


class ItemCreateRequest(BaseModel):
    name: str
    price: float


class ItemPutRequest(BaseModel):
    name: str
    price: float


class ItemPatchRequest(BaseModel):
    # extra="forbid" отклоняет как неизвестные поля, так и попытку поменять
    # "deleted" (его в модели просто нет).
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    price: Optional[float] = None


class CartItem(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class Cart(BaseModel):
    id: int
    items: list[CartItem]
    price: float


# --------------------------------------------------------------------------
# Хранилище (hw4: MySQL через SQLAlchemy, вместо словарей в памяти)
# --------------------------------------------------------------------------


def _db() -> Session:
    session = get_session()
    try:
        yield session
    finally:
        session.close()


def _to_item(orm_item: ItemOrm) -> Item:
    return Item(id=orm_item.id, name=orm_item.name, price=orm_item.price, deleted=orm_item.deleted)


def _get_item_or_404(session: Session, item_id: int) -> ItemOrm:
    """Ищет товар независимо от флага deleted (нужно для PUT/PATCH/DELETE)."""
    item = session.get(ItemOrm, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


def _get_visible_item_or_404(session: Session, item_id: int) -> ItemOrm:
    """Для публичного GET: удалённый товар считается не найденным."""
    item = _get_item_or_404(session, item_id)
    if item.deleted:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


def _build_cart(session: Session, cart_id: int) -> Cart:
    rows = (
        session.query(CartItemOrm, ItemOrm)
        .join(ItemOrm, CartItemOrm.item_id == ItemOrm.id)
        .filter(CartItemOrm.cart_id == cart_id)
        .all()
    )

    cart_items: list[CartItem] = []
    price = 0.0

    for cart_item, item in rows:
        cart_items.append(
            CartItem(id=item.id, name=item.name, quantity=cart_item.quantity, available=not item.deleted)
        )
        price += item.price * cart_item.quantity

    return Cart(id=cart_id, items=cart_items, price=price)


# --------------------------------------------------------------------------
# item
# --------------------------------------------------------------------------


@app.post("/item", status_code=201, response_model=Item)
def create_item(body: ItemCreateRequest, session: Session = Depends(_db)) -> Item:
    orm_item = ItemOrm(name=body.name, price=body.price, deleted=False)
    session.add(orm_item)
    session.commit()
    session.refresh(orm_item)
    return _to_item(orm_item)


@app.get("/item/{item_id}", response_model=Item)
def get_item(item_id: int, session: Session = Depends(_db)) -> Item:
    return _to_item(_get_visible_item_or_404(session, item_id))


@app.get("/item", response_model=list[Item])
def get_item_list(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    show_deleted: bool = Query(False),
    session: Session = Depends(_db),
) -> list[Item]:
    query = session.query(ItemOrm)

    if not show_deleted:
        query = query.filter(ItemOrm.deleted.is_(False))
    if min_price is not None:
        query = query.filter(ItemOrm.price >= min_price)
    if max_price is not None:
        query = query.filter(ItemOrm.price <= max_price)

    query = query.order_by(ItemOrm.id).offset(offset).limit(limit)

    return [_to_item(item) for item in query.all()]


@app.put("/item/{item_id}", response_model=Item)
def put_item(item_id: int, body: ItemPutRequest, session: Session = Depends(_db)) -> Item:
    item = _get_item_or_404(session, item_id)
    item.name = body.name
    item.price = body.price
    session.commit()
    session.refresh(item)
    return _to_item(item)


@app.patch("/item/{item_id}")
def patch_item(item_id: int, body: ItemPatchRequest, session: Session = Depends(_db)):
    item = _get_item_or_404(session, item_id)

    if item.deleted:
        return Response(status_code=304)

    if body.name is not None:
        item.name = body.name
    if body.price is not None:
        item.price = body.price

    session.commit()
    session.refresh(item)
    return _to_item(item)


@app.delete("/item/{item_id}")
def delete_item(item_id: int, session: Session = Depends(_db)) -> Item:
    item = _get_item_or_404(session, item_id)
    item.deleted = True
    session.commit()
    session.refresh(item)
    return _to_item(item)


# --------------------------------------------------------------------------
# cart
# --------------------------------------------------------------------------


@app.post("/cart", status_code=201)
def create_cart(response: Response, session: Session = Depends(_db)) -> dict[str, int]:
    cart = CartOrm()
    session.add(cart)
    session.commit()
    session.refresh(cart)
    response.headers["location"] = f"/cart/{cart.id}"
    return {"id": cart.id}


@app.get("/cart/{cart_id}", response_model=Cart)
def get_cart(cart_id: int, session: Session = Depends(_db)) -> Cart:
    if session.get(CartOrm, cart_id) is None:
        raise HTTPException(status_code=404, detail="Cart not found")
    return _build_cart(session, cart_id)


@app.get("/cart", response_model=list[Cart])
def get_cart_list(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    min_quantity: Optional[int] = Query(None, ge=0),
    max_quantity: Optional[int] = Query(None, ge=0),
    session: Session = Depends(_db),
) -> list[Cart]:
    cart_ids = [row[0] for row in session.query(CartOrm.id).order_by(CartOrm.id).all()]

    result: list[Cart] = []
    for cart_id in cart_ids:
        cart = _build_cart(session, cart_id)
        total_quantity = sum(ci.quantity for ci in cart.items)

        if min_price is not None and cart.price < min_price:
            continue
        if max_price is not None and cart.price > max_price:
            continue
        if min_quantity is not None and total_quantity < min_quantity:
            continue
        if max_quantity is not None and total_quantity > max_quantity:
            continue

        result.append(cart)

    return result[offset : offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}", response_model=Cart)
def add_item_to_cart(cart_id: int, item_id: int, session: Session = Depends(_db)) -> Cart:
    if session.get(CartOrm, cart_id) is None:
        raise HTTPException(status_code=404, detail="Cart not found")

    _get_item_or_404(session, item_id)  # товар должен существовать (удалённый тоже ок)

    cart_item = (
        session.query(CartItemOrm)
        .filter_by(cart_id=cart_id, item_id=item_id)
        .first()
    )
    if cart_item is None:
        cart_item = CartItemOrm(cart_id=cart_id, item_id=item_id, quantity=1)
        session.add(cart_item)
    else:
        cart_item.quantity += 1

    session.commit()

    return _build_cart(session, cart_id)


# --------------------------------------------------------------------------
# Доп. задание: WebSocket чат по комнатам
# --------------------------------------------------------------------------

_chat_rooms: dict[str, dict[WebSocket, str]] = defaultdict(dict)


def _random_username() -> str:
    return f"user-{random.randint(1000, 9999)}"


@app.websocket("/chat/{chat_name}")
async def chat(websocket: WebSocket, chat_name: str) -> None:
    await websocket.accept()

    username = _random_username()
    room = _chat_rooms[chat_name]
    room[websocket] = username

    try:
        while True:
            message = await websocket.receive_text()
            formatted = f"{username} :: {message}"
            for peer in list(room):
                if peer is websocket:
                    continue
                await peer.send_text(formatted)
    except WebSocketDisconnect:
        pass
    finally:
        room.pop(websocket, None)
        if not room:
            _chat_rooms.pop(chat_name, None)
