from collections import defaultdict
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field, field_validator
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import select
from sqlalchemy.orm import Session

from shop_api.database import CartItemRecord, CartRecord, ItemRecord, get_session

app = FastAPI(title="Shop API")
Instrumentator(excluded_handlers=["/metrics"]).instrument(app).expose(app)


class ItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    price: Annotated[float, Field(ge=0)]


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    price: Annotated[float | None, Field(ge=0)] = None

    @field_validator("name", "price")
    @classmethod
    def reject_null(cls, value: str | float | None) -> str | float:
        if value is None:
            raise ValueError("value must not be null")
        return value


def item_response(item: ItemRecord) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "price": item.price,
        "deleted": item.deleted,
    }


def item_or_404(
    session: Session, item_id: int, include_deleted: bool = False
) -> ItemRecord:
    item = session.get(ItemRecord, item_id)
    if item is None or (item.deleted and not include_deleted):
        raise HTTPException(status_code=404, detail="Item not found")
    return item


def cart_or_404(session: Session, cart_id: int) -> CartRecord:
    cart = session.get(CartRecord, cart_id)
    if cart is None:
        raise HTTPException(status_code=404, detail="Cart not found")
    return cart


def cart_response(session: Session, cart: CartRecord) -> dict:
    lines = session.execute(
        select(CartItemRecord, ItemRecord)
        .join(ItemRecord, ItemRecord.id == CartItemRecord.item_id)
        .where(CartItemRecord.cart_id == cart.id)
        .order_by(CartItemRecord.id)
    ).all()
    cart_items = [
        {
            "id": item.id,
            "name": item.name,
            "quantity": line.quantity,
            "available": not item.deleted,
        }
        for line, item in lines
    ]
    price = sum(item.price * line.quantity for line, item in lines)
    return {"id": cart.id, "items": cart_items, "price": price}


@app.post("/cart", status_code=201)
def create_cart(
    response: Response,
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, int]:
    cart = CartRecord()
    session.add(cart)
    session.commit()
    session.refresh(cart)
    response.headers["Location"] = f"/cart/{cart.id}"
    return {"id": cart.id}


@app.get("/cart/{cart_id}")
def get_cart(
    cart_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    cart = cart_or_404(session, cart_id)
    return cart_response(session, cart)


@app.get("/cart")
def get_carts(
    session: Annotated[Session, Depends(get_session)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    min_quantity: Annotated[int | None, Query(ge=0)] = None,
    max_quantity: Annotated[int | None, Query(ge=0)] = None,
) -> list[dict]:
    result = []
    carts = session.scalars(select(CartRecord).order_by(CartRecord.id)).all()
    for cart in carts:
        data = cart_response(session, cart)
        quantity = sum(line["quantity"] for line in data["items"])
        if min_price is not None and data["price"] < min_price:
            continue
        if max_price is not None and data["price"] > max_price:
            continue
        if min_quantity is not None and quantity < min_quantity:
            continue
        if max_quantity is not None and quantity > max_quantity:
            continue
        result.append(data)
    return result[offset : offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}")
def add_to_cart(
    cart_id: int,
    item_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    # Lock the parent cart, which exists even when this is the first item.
    # This serializes simultaneous first additions on PostgreSQL.
    cart = session.scalar(
        select(CartRecord)
        .where(CartRecord.id == cart_id)
        .with_for_update()
    )
    if cart is None:
        raise HTTPException(status_code=404, detail="Cart not found")
    item_or_404(session, item_id)
    line = session.scalar(
        select(CartItemRecord)
        .where(CartItemRecord.cart_id == cart_id, CartItemRecord.item_id == item_id)
        .with_for_update()
    )
    if line is None:
        line = CartItemRecord(cart_id=cart_id, item_id=item_id, quantity=1)
        session.add(line)
    else:
        line.quantity += 1
    session.commit()
    return cart_response(session, cart)


@app.post("/item", status_code=201)
def create_item(
    data: ItemCreate,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    item = ItemRecord(**data.model_dump())
    session.add(item)
    session.commit()
    session.refresh(item)
    response.headers["Location"] = f"/item/{item.id}"
    return item_response(item)


@app.get("/item/{item_id}")
def get_item(
    item_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    return item_response(item_or_404(session, item_id))


@app.get("/item")
def get_items(
    session: Annotated[Session, Depends(get_session)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    show_deleted: bool = False,
) -> list[dict]:
    query = select(ItemRecord)
    if not show_deleted:
        query = query.where(ItemRecord.deleted.is_(False))
    if min_price is not None:
        query = query.where(ItemRecord.price >= min_price)
    if max_price is not None:
        query = query.where(ItemRecord.price <= max_price)
    items = session.scalars(
        query.order_by(ItemRecord.id).offset(offset).limit(limit)
    ).all()
    return [item_response(item) for item in items]


@app.put("/item/{item_id}")
def replace_item(
    item_id: int,
    data: ItemCreate,
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    item = item_or_404(session, item_id, include_deleted=True)
    item.name = data.name
    item.price = data.price
    session.commit()
    return item_response(item)


@app.patch("/item/{item_id}")
def update_item(
    item_id: int,
    data: ItemPatch,
    session: Annotated[Session, Depends(get_session)],
):
    item = item_or_404(session, item_id, include_deleted=True)
    if item.deleted:
        return Response(status_code=304)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    session.commit()
    return item_response(item)


@app.delete("/item/{item_id}")
def delete_item(
    item_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, int]:
    item = item_or_404(session, item_id, include_deleted=True)
    item.deleted = True
    session.commit()
    return {"id": item_id}


chat_rooms: dict[str, dict[WebSocket, str]] = defaultdict(dict)


@app.websocket("/chat/{chat_name}")
async def chat(websocket: WebSocket, chat_name: str) -> None:
    await websocket.accept()
    username = uuid4().hex[:8]
    chat_rooms[chat_name][websocket] = username

    try:
        while True:
            message = await websocket.receive_text()
            text = f"{username} :: {message}"
            for client in list(chat_rooms[chat_name]):
                if client is not websocket:
                    try:
                        await client.send_text(text)
                    except (WebSocketDisconnect, RuntimeError):
                        chat_rooms[chat_name].pop(client, None)
    except WebSocketDisconnect:
        pass
    finally:
        room = chat_rooms.get(chat_name)
        if room is not None:
            room.pop(websocket, None)
            if not room:
                del chat_rooms[chat_name]
