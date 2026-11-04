"""Shop API: REST + RPC API магазина, данные хранятся в БД (SQLAlchemy)."""

from collections import defaultdict
from http import HTTPStatus
from typing import Annotated
from uuid import uuid4

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import NonNegativeFloat, NonNegativeInt, PositiveInt
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from shop_api.contracts import (
    CartCreatedResponse,
    CartItemResponse,
    CartResponse,
    ItemRequest,
    ItemResponse,
    PatchItemRequest,
)
from shop_api.database import get_session, init_db
from shop_api.models import CartItemORM, CartORM, ItemORM

app = FastAPI(title="Shop API")
init_db()

SessionDep = Annotated[Session, Depends(get_session)]


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------


def _not_found(resource: str, resource_id: int) -> HTTPException:
    return HTTPException(HTTPStatus.NOT_FOUND, f"Request resource /{resource}/{resource_id} was not found")


def _get_active_item(session: Session, item_id: int) -> ItemORM:
    """Возвращает не удаленный товар или кидает 404."""
    item = session.get(ItemORM, item_id)
    if item is None or item.deleted:
        raise _not_found("item", item_id)
    return item


# Цена и количество корзины считаются прямо в БД: сумма (количество * цена) по ее товарам.
_CART_PRICE = func.coalesce(func.sum(CartItemORM.quantity * ItemORM.price), 0.0)
_CART_QUANTITY = func.coalesce(func.sum(CartItemORM.quantity), 0)


def _carts_totals():
    return (
        select(CartORM.id, _CART_PRICE.label("price"))
        .outerjoin(CartItemORM, CartItemORM.cart_id == CartORM.id)
        .outerjoin(ItemORM, ItemORM.id == CartItemORM.item_id)
        .group_by(CartORM.id)
        .order_by(CartORM.id)
    )


def _build_carts(session: Session, totals: list[tuple[int, float]]) -> list[CartResponse]:
    """Собирает ответы по корзинам: одним запросом подгружает товары всех корзин."""
    cart_ids = [cart_id for cart_id, _ in totals]
    rows = session.execute(
        select(CartItemORM.cart_id, ItemORM, CartItemORM.quantity)
        .join(ItemORM, ItemORM.id == CartItemORM.item_id)
        .where(CartItemORM.cart_id.in_(cart_ids))
        .order_by(CartItemORM.cart_id, ItemORM.id)
    ).all()

    items_by_cart: dict[int, list[CartItemResponse]] = defaultdict(list)
    for cart_id, item, quantity in rows:
        items_by_cart[cart_id].append(
            CartItemResponse(id=item.id, name=item.name, quantity=quantity, available=not item.deleted)
        )

    return [CartResponse(id=cart_id, items=items_by_cart[cart_id], price=price) for cart_id, price in totals]


# ---------------------------------------------------------------------------
# cart
# ---------------------------------------------------------------------------


@app.post("/cart", status_code=HTTPStatus.CREATED)
def post_cart(response: Response, session: SessionDep) -> CartCreatedResponse:
    """RPC: создает пустую корзину, тело не принимает, возвращает ее id."""
    cart = CartORM()
    session.add(cart)
    session.commit()

    response.headers["location"] = f"/cart/{cart.id}"
    return CartCreatedResponse(id=cart.id)


@app.get("/cart/{id}")
def get_cart(id: int, session: SessionDep) -> CartResponse:
    totals = session.execute(_carts_totals().where(CartORM.id == id)).all()
    if not totals:
        raise _not_found("cart", id)
    return _build_carts(session, totals)[0]


@app.get("/cart")
def get_cart_list(
    session: SessionDep,
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    min_quantity: Annotated[NonNegativeInt | None, Query()] = None,
    max_quantity: Annotated[NonNegativeInt | None, Query()] = None,
) -> list[CartResponse]:
    query = _carts_totals()

    # Фильтры по агрегатам (сумма, количество) - это HAVING, а не WHERE
    if min_price is not None:
        query = query.having(_CART_PRICE >= min_price)
    if max_price is not None:
        query = query.having(_CART_PRICE <= max_price)
    if min_quantity is not None:
        query = query.having(_CART_QUANTITY >= min_quantity)
    if max_quantity is not None:
        query = query.having(_CART_QUANTITY <= max_quantity)

    totals = session.execute(query.offset(offset).limit(limit)).all()
    return _build_carts(session, totals)


@app.post("/cart/{cart_id}/add/{item_id}")
def post_cart_add_item(cart_id: int, item_id: int, session: SessionDep) -> CartResponse:
    """RPC: кладет товар в корзину (если он уже там, увеличивает количество)."""
    # FOR UPDATE: параллельные добавления в одну корзину выполняются по очереди,
    # поэтому количество не теряется
    cart = session.get(CartORM, cart_id, with_for_update=True)
    if cart is None:
        raise _not_found("cart", cart_id)
    _get_active_item(session, item_id)

    link = session.get(CartItemORM, (cart_id, item_id))
    if link is None:
        session.add(CartItemORM(cart_id=cart_id, item_id=item_id, quantity=1))
    else:
        link.quantity += 1
    session.commit()

    return get_cart(cart_id, session)


# ---------------------------------------------------------------------------
# item
# ---------------------------------------------------------------------------


@app.post("/item", status_code=HTTPStatus.CREATED)
def post_item(body: ItemRequest, response: Response, session: SessionDep) -> ItemResponse:
    item = ItemORM(name=body.name, price=body.price, deleted=False)
    session.add(item)
    session.commit()

    response.headers["location"] = f"/item/{item.id}"
    return ItemResponse.model_validate(item)


@app.get("/item/{id}")
def get_item(id: int, session: SessionDep) -> ItemResponse:
    return ItemResponse.model_validate(_get_active_item(session, id))


@app.get("/item")
def get_item_list(
    session: SessionDep,
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    show_deleted: Annotated[bool, Query()] = False,
) -> list[ItemResponse]:
    query = select(ItemORM).order_by(ItemORM.id)

    if not show_deleted:
        query = query.where(ItemORM.deleted.is_(False))
    if min_price is not None:
        query = query.where(ItemORM.price >= min_price)
    if max_price is not None:
        query = query.where(ItemORM.price <= max_price)

    items = session.scalars(query.offset(offset).limit(limit)).all()
    return [ItemResponse.model_validate(item) for item in items]


@app.put(
    "/item/{id}",
    responses={HTTPStatus.NOT_MODIFIED: {"description": "Item is deleted and can not be replaced"}},
)
def put_item(id: int, body: ItemRequest, response: Response, session: SessionDep) -> ItemResponse | None:
    """Полная замена существующего товара (создание через PUT запрещено)."""
    item = session.get(ItemORM, id)
    if item is None:
        raise _not_found("item", id)
    if item.deleted:
        response.status_code = HTTPStatus.NOT_MODIFIED
        return None

    item.name = body.name
    item.price = body.price
    session.commit()
    return ItemResponse.model_validate(item)


@app.patch(
    "/item/{id}",
    responses={HTTPStatus.NOT_MODIFIED: {"description": "Item is deleted and can not be changed"}},
)
def patch_item(id: int, body: PatchItemRequest, response: Response, session: SessionDep) -> ItemResponse | None:
    """Частичное обновление товара (менять `deleted` нельзя)."""
    item = session.get(ItemORM, id)
    if item is None:
        raise _not_found("item", id)
    if item.deleted:
        response.status_code = HTTPStatus.NOT_MODIFIED
        return None

    for field_name in body.model_fields_set:
        setattr(item, field_name, getattr(body, field_name))
    session.commit()
    return ItemResponse.model_validate(item)


@app.delete("/item/{id}")
def delete_item(id: int, session: SessionDep) -> Response:
    """Помечает товар удаленным. Повторное удаление тоже возвращает 200."""
    item = session.get(ItemORM, id)
    if item is None:
        raise _not_found("item", id)

    item.deleted = True
    session.commit()
    return Response(status_code=HTTPStatus.OK)


# ---------------------------------------------------------------------------
# Доп. задание ДЗ2: WebSocket-чат с комнатами
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
