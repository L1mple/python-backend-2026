from fastapi import FastAPI, HTTPException, Query, Response, WebSocket
from pydantic import BaseModel, ConfigDict

from http import HTTPStatus
from typing import Annotated

from random import choice, randint
from dataclasses import dataclass, field

from fastapi import WebSocketDisconnect
from pydantic import NonNegativeInt, PositiveInt


app = FastAPI(title="Shop API")

_items = {}
_carts = {}

_item_n = 0
_cart_n = 0


class ItemBody(BaseModel):
    name: str
    price: float


class PatchBody(BaseModel):
    name: str | None = None
    price: float | None = None

    model_config = ConfigDict(extra="forbid")


def cart_view(cid):

    stuff = []
    s = 0.0

    for line in _carts[cid]:
        goods = _items[line["item_id"]]

        stuff.append({
            "id": goods["id"],
            "name": goods["name"],
            "quantity": line["qty"],
            "available": goods["deleted"] == False,
        })

        s += goods["price"] * line["qty"]

    return {"id": cid, "items": stuff, "price": s}


@app.post("/cart", status_code=HTTPStatus.CREATED)
def post_cart(response: Response):

    global _cart_n

    _cart_n = _cart_n + 1
    _carts[_cart_n] = []
    # as REST states one should provide uri to newly created resource in location header
    response.headers["location"] = "/cart/" + str(_cart_n)

    return {"id": _cart_n}


@app.get("/cart/{id}")
def get_cart(id: int):

    if id not in _carts:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Request resource /cart/{id} was not found")
    
    return cart_view(id)


@app.get("/cart")
def get_cart_list(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    min_quantity: int | None = Query(None, ge=0),
    max_quantity: int | None = Query(None, ge=0),
):
    all_carts = []
    for cid in _carts:
        one = cart_view(cid)
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

    if cart_id not in _carts:
        raise HTTPException(404)
    if item_id not in _items:
        raise HTTPException(404)
    if _items[item_id]["deleted"]:
        raise HTTPException(404)

    already = False
    for line in _carts[cart_id]:
        if line["item_id"] == item_id:
            line["qty"] += 1
            already = True
            break
    if not already:
        _carts[cart_id].append({"item_id": item_id, "qty": 1})

    return cart_view(cart_id)


@app.post("/item", status_code=201)
def post_item(info: ItemBody):

    global _item_n
    _item_n += 1
    row = {"id": _item_n, "name": info.name, "price": info.price, "deleted": False}
    _items[_item_n] = row

    return row


@app.get("/item/{id}")
def get_item(id: int):

    if id not in _items:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Request resource /item/{id} was not found",
        )
    row = _items[id]
    if row["deleted"]:
        raise HTTPException(HTTPStatus.NOT_FOUND)
    
    return row


@app.get("/item")
def get_items(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    show_deleted: bool = False,
):
    acc = []
    for row in _items.values():
        if row["deleted"] and not show_deleted:
            continue
        if min_price is not None and row["price"] < min_price:
            continue
        if max_price is not None and row["price"] > max_price:
            continue
        acc.append(row)

    curr = 0
    page = []
    for row in acc:
        if offset <= curr < offset + limit:
            page.append(row)
        curr += 1

    return page


@app.put("/item/{id}")
def put_item(id: int, info: ItemBody):

    if id not in _items:
        raise HTTPException(404, "нет такого")
    old = _items[id]
    _items[id] = {
        "id": id,
        "name": info.name,
        "price": info.price,
        "deleted": old["deleted"],
    }

    return _items[id]


@app.patch("/item/{id}")
def patch_item(id: int, info: PatchBody):

    if id not in _items:
        raise HTTPException(HTTPStatus.NOT_FOUND)

    row = _items[id]
    if row["deleted"]:
        raise HTTPException(
            HTTPStatus.NOT_MODIFIED,
            f"Requested resource /item/{id} was not found",
        )

    if info.name is not None:
        row["name"] = info.name
    if info.price is not None:
        row["price"] = info.price

    return row


@app.delete("/item/{id}")
def delete_item(id: int):
    if id not in _items:
        raise HTTPException(HTTPStatus.NOT_FOUND)
    _items[id]["deleted"] = True
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
