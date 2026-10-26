from fastapi import FastAPI, HTTPException, Query, Response, WebSocket
from pydantic import BaseModel, ConfigDict
from prometheus_fastapi_instrumentator import Instrumentator

from http import HTTPStatus
from typing import Annotated
from contextlib import contextmanager

from random import choice, randint
from dataclasses import dataclass, field

from fastapi import WebSocketDisconnect
from pydantic import NonNegativeInt, PositiveInt

from shop_api.db import Cart, CartLine, Item, SessionLocal


app = FastAPI(title="Shop API")
Instrumentator().instrument(app).expose(app)


class ItemBody(BaseModel):
    name: str
    price: float


class PatchBody(BaseModel):
    name: str | None = None
    price: float | None = None

    model_config = ConfigDict(extra="forbid")


@contextmanager
def open_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def item_out(row):
    return {
        "id": row.id,
        "name": row.name,
        "price": row.price,
        "deleted": bool(row.deleted),
    }


def cart_view(db, cid):
    stuff = []
    s = 0.0
    lines = db.query(CartLine).filter(CartLine.cart_id == cid).order_by(CartLine.item_id).all()
    for line in lines:
        goods = db.get(Item, line.item_id)
        stuff.append({
            "id": goods.id,
            "name": goods.name,
            "quantity": line.qty,
            "available": goods.deleted == False,
        })
        s += goods.price * line.qty
    return {"id": cid, "items": stuff, "price": float(s)}


@app.post("/cart", status_code=HTTPStatus.CREATED)
def post_cart(response: Response):
    with open_db() as db:
        cart = Cart()
        db.add(cart)
        db.flush()
        response.headers["location"] = "/cart/" + str(cart.id)
        return {"id": cart.id}


@app.get("/cart/{id}")
def get_cart(id: int):
    with open_db() as db:
        if db.get(Cart, id) is None:
            raise HTTPException(HTTPStatus.NOT_FOUND, f"Request resource /cart/{id} was not found")
        return cart_view(db, id)


@app.get("/cart")
def get_cart_list(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    min_quantity: int | None = Query(None, ge=0),
    max_quantity: int | None = Query(None, ge=0),
):
    with open_db() as db:
        all_carts = []
        for cart in db.query(Cart).order_by(Cart.id).all():
            one = cart_view(db, cart.id)
            q = 0
            for x in one["items"]:
                q += x["quantity"]

            if min_price is not None:
                if one["price"] < min_price:
                    continue
            if max_price is not None:
                if one["price"] > max_price:
                    continue
            if min_quantity is not None and q < min_quantity:
                continue
            if max_quantity is not None and q > max_quantity:
                continue
            all_carts.append(one)

        return all_carts[offset : offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}")
def add_to_cart(cart_id: int, item_id: int):
    with open_db() as db:
        if db.get(Cart, cart_id) is None:
            raise HTTPException(404)
        goods = db.get(Item, item_id)
        if goods is None or goods.deleted:
            raise HTTPException(404)

        line = db.get(CartLine, (cart_id, item_id))
        if line is None:
            db.add(CartLine(cart_id=cart_id, item_id=item_id, qty=1))
        else:
            line.qty += 1
        db.flush()
        return cart_view(db, cart_id)


@app.post("/item", status_code=201)
def post_item(info: ItemBody):
    with open_db() as db:
        row = Item(name=info.name, price=info.price, deleted=False)
        db.add(row)
        db.flush()
        return item_out(row)


@app.get("/item/{id}")
def get_item(id: int):
    with open_db() as db:
        row = db.get(Item, id)
        if row is None:
            raise HTTPException(
                HTTPStatus.NOT_FOUND,
                f"Request resource /item/{id} was not found",
            )
        if row.deleted:
            raise HTTPException(HTTPStatus.NOT_FOUND)
        return item_out(row)


@app.get("/item")
def get_items(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    show_deleted: bool = False,
):
    with open_db() as db:
        acc = []
        for row in db.query(Item).order_by(Item.id).all():
            if row.deleted and not show_deleted:
                continue
            if min_price is not None and row.price < min_price:
                continue
            if max_price is not None and row.price > max_price:
                continue
            acc.append(item_out(row))

        curr = 0
        page = []
        for row in acc:
            if offset <= curr < offset + limit:
                page.append(row)
            curr += 1
        return page


@app.put("/item/{id}")
def put_item(id: int, info: ItemBody):
    with open_db() as db:
        old = db.get(Item, id)
        if old is None:
            raise HTTPException(404, "нет такого")
        old.name = info.name
        old.price = info.price
        db.flush()
        return item_out(old)


@app.patch("/item/{id}")
def patch_item(id: int, info: PatchBody):
    with open_db() as db:
        row = db.get(Item, id)
        if row is None:
            raise HTTPException(HTTPStatus.NOT_FOUND)
        if row.deleted:
            raise HTTPException(
                HTTPStatus.NOT_MODIFIED,
                f"Requested resource /item/{id} was not found",
            )
        if info.name is not None:
            row.name = info.name
        if info.price is not None:
            row.price = info.price
        db.flush()
        return item_out(row)


@app.delete("/item/{id}")
def delete_item(id: int):
    with open_db() as db:
        row = db.get(Item, id)
        if row is None:
            raise HTTPException(HTTPStatus.NOT_FOUND)
        row.deleted = True
        return Response("")


@dataclass(slots=True)
class Broadcaster:
    subscribers: list[WebSocket] = field(init=False, default_factory=list)

    async def subscribe(self, ws: WebSocket) -> None:
        await ws.accept()
        self.subscribers.append(ws)

    def unsubscribe(self, ws: WebSocket) -> None:
        self.subscribers.remove(ws)

    async def publish(self, message: str, skip=None) -> None:
        for ws in self.subscribers:
            if ws is skip:
                continue
            await ws.send_text(message)


_rooms = {}
_nicks = ["кот", "пёс", "енот", "лось", "лис"]


@app.websocket("/chat/{chat_name}")
async def ws_chat(ws: WebSocket, chat_name: str):
    if chat_name not in _rooms:
        _rooms[chat_name] = Broadcaster()
    room = _rooms[chat_name]
    nick = choice(_nicks) + str(randint(10, 99))
    await room.subscribe(ws)

    try:
        while True:
            text = await ws.receive_text()
            await room.publish(f"{nick} :: {text}", skip=ws)
    except WebSocketDisconnect:
        room.unsubscribe(ws)
