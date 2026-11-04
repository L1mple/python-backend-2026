from collections import defaultdict
from http import HTTPStatus
from itertools import count
from threading import Lock
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
from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, NonNegativeInt, PositiveInt, model_validator

app = FastAPI(title="Shop API")


# ---------------------------------------------------------------------------
# Контракты (запросы и ответы)
# ---------------------------------------------------------------------------


class ItemRequest(BaseModel):
    """Тело POST /item и PUT /item/{id}: товар целиком."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    price: NonNegativeFloat


class PatchItemRequest(BaseModel):
    """Тело PATCH /item/{id}: любое подмножество полей, кроме `deleted`."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1)
    price: NonNegativeFloat | None = None

    @model_validator(mode="after")
    def _no_explicit_nulls(self) -> "PatchItemRequest":
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} must not be null")
        return self


class ItemResponse(BaseModel):
    id: int
    name: str
    price: float
    deleted: bool = False


class CartItemResponse(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class CartResponse(BaseModel):
    id: int
    items: list[CartItemResponse]
    price: float


class CartCreatedResponse(BaseModel):
    id: int


# ---------------------------------------------------------------------------
# Хранилище (в оперативной памяти)
# ---------------------------------------------------------------------------

_lock = Lock()
_item_ids = count(1)
_cart_ids = count(1)

_items: dict[int, ItemResponse] = {}
_carts: dict[int, dict[int, int]] = {}  # cart_id -> {item_id: quantity}


def _get_active_item(item_id: int) -> ItemResponse:
    """Возвращает не удаленный товар или кидает 404."""
    item = _items.get(item_id)
    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Request resource /item/{item_id} was not found")
    return item


def _get_cart(cart_id: int) -> dict[int, int]:
    cart = _carts.get(cart_id)
    if cart is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Request resource /cart/{cart_id} was not found")
    return cart


def _render_cart(cart_id: int, content: dict[int, int]) -> CartResponse:
    items = []
    price = 0.0
    for item_id, quantity in content.items():
        item = _items[item_id]
        items.append(
            CartItemResponse(
                id=item.id,
                name=item.name,
                quantity=quantity,
                available=not item.deleted,
            )
        )
        price += item.price * quantity
    return CartResponse(id=cart_id, items=items, price=price)


# ---------------------------------------------------------------------------
# cart
# ---------------------------------------------------------------------------


@app.post("/cart", status_code=HTTPStatus.CREATED)
def post_cart(response: Response) -> CartCreatedResponse:
    """RPC: создает пустую корзину, тело не принимает, возвращает ее id."""
    with _lock:
        cart_id = next(_cart_ids)
        _carts[cart_id] = {}

    response.headers["location"] = f"/cart/{cart_id}"
    return CartCreatedResponse(id=cart_id)


@app.get("/cart/{id}")
def get_cart(id: int) -> CartResponse:
    with _lock:
        return _render_cart(id, _get_cart(id))


@app.get("/cart")
def get_cart_list(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    min_quantity: Annotated[NonNegativeInt | None, Query()] = None,
    max_quantity: Annotated[NonNegativeInt | None, Query()] = None,
) -> list[CartResponse]:
    with _lock:
        carts = [_render_cart(cart_id, content) for cart_id, content in _carts.items()]

    def matches(cart: CartResponse) -> bool:
        total_quantity = sum(item.quantity for item in cart.items)
        return (
            (min_price is None or cart.price >= min_price)
            and (max_price is None or cart.price <= max_price)
            and (min_quantity is None or total_quantity >= min_quantity)
            and (max_quantity is None or total_quantity <= max_quantity)
        )

    return [cart for cart in carts if matches(cart)][offset : offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}")
def post_cart_add_item(cart_id: int, item_id: int) -> CartResponse:
    """RPC: кладет товар в корзину (если он уже там, увеличивает количество)."""
    with _lock:
        cart = _get_cart(cart_id)
        _get_active_item(item_id)
        cart[item_id] = cart.get(item_id, 0) + 1
        return _render_cart(cart_id, cart)


# ---------------------------------------------------------------------------
# item
# ---------------------------------------------------------------------------


@app.post("/item", status_code=HTTPStatus.CREATED)
def post_item(body: ItemRequest, response: Response) -> ItemResponse:
    with _lock:
        item = ItemResponse(id=next(_item_ids), name=body.name, price=body.price)
        _items[item.id] = item

    response.headers["location"] = f"/item/{item.id}"
    return item


@app.get("/item/{id}")
def get_item(id: int) -> ItemResponse:
    with _lock:
        return _get_active_item(id)


@app.get("/item")
def get_item_list(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    show_deleted: Annotated[bool, Query()] = False,
) -> list[ItemResponse]:
    with _lock:
        items = list(_items.values())

    filtered = [
        item
        for item in items
        if (show_deleted or not item.deleted)
        and (min_price is None or item.price >= min_price)
        and (max_price is None or item.price <= max_price)
    ]
    return filtered[offset : offset + limit]


@app.put(
    "/item/{id}",
    responses={HTTPStatus.NOT_MODIFIED: {"description": "Item is deleted and can not be replaced"}},
)
def put_item(id: int, body: ItemRequest, response: Response) -> ItemResponse | None:
    """Полная замена существующего товара (создание через PUT запрещено)."""
    with _lock:
        item = _items.get(id)
        if item is None:
            raise HTTPException(HTTPStatus.NOT_FOUND, f"Request resource /item/{id} was not found")
        if item.deleted:
            response.status_code = HTTPStatus.NOT_MODIFIED
            return None

        item.name = body.name
        item.price = body.price
        return item


@app.patch(
    "/item/{id}",
    responses={HTTPStatus.NOT_MODIFIED: {"description": "Item is deleted and can not be changed"}},
)
def patch_item(id: int, body: PatchItemRequest, response: Response) -> ItemResponse | None:
    """Частичное обновление товара (менять `deleted` нельзя)."""
    with _lock:
        item = _items.get(id)
        if item is None:
            raise HTTPException(HTTPStatus.NOT_FOUND, f"Request resource /item/{id} was not found")
        if item.deleted:
            response.status_code = HTTPStatus.NOT_MODIFIED
            return None

        for field_name in body.model_fields_set:
            setattr(item, field_name, getattr(body, field_name))
        return item


@app.delete("/item/{id}")
def delete_item(id: int) -> Response:
    """Помечает товар удаленным. Повторное удаление тоже возвращает 200."""
    with _lock:
        item = _items.get(id)
        if item is None:
            raise HTTPException(HTTPStatus.NOT_FOUND, f"Request resource /item/{id} was not found")
        item.deleted = True

    return Response(status_code=HTTPStatus.OK)


# ---------------------------------------------------------------------------
# Доп. задание: WebSocket-чат с комнатами
# ---------------------------------------------------------------------------

_chat_rooms: dict[str, dict[WebSocket, str]] = defaultdict(dict)  # room -> {ws: username}


@app.websocket("/chat/{chat_name}")
async def ws_chat(ws: WebSocket, chat_name: str) -> None:
    await ws.accept()

    username = uuid4().hex[:8]
    room = _chat_rooms[chat_name]
    room[ws] = username

    try:
        while True:
            message = await ws.receive_text()
            text = f"{username} :: {message}"

            for other in list(room):
                if other is not ws:
                    await other.send_text(text)
    except WebSocketDisconnect:
        pass
    finally:
        room.pop(ws, None)
        if not room:
            _chat_rooms.pop(chat_name, None)
