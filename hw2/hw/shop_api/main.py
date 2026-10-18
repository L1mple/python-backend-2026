from http import HTTPStatus
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import NonNegativeInt, PositiveInt
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .chat import router as chat_router
from .database import create_tables, get_session
from .db_models import CartLineRecord, CartRecord, ItemRecord
from .models import Cart, CartCreated, Item, ItemData, ItemPatch
from .store import Store

app = FastAPI(title="Shop API")
app.include_router(chat_router)
Instrumentator(excluded_handlers=["/metrics"]).instrument(app).expose(
    app, include_in_schema=False
)
create_tables()

PriceFilter = Annotated[float | None, Query(ge=0, allow_inf_nan=False)]
Offset = Annotated[NonNegativeInt, Query()]
Limit = Annotated[PositiveInt, Query()]
QuantityFilter = Annotated[NonNegativeInt | None, Query()]
DatabaseSession = Annotated[Session, Depends(get_session)]


def to_item(record: ItemRecord) -> Item:
    return Item(
        id=record.id,
        name=record.name,
        price=record.price,
        deleted=record.deleted,
    )


def find_item(
    session: Session, item_id: int, include_deleted: bool = False
) -> ItemRecord:
    item = session.get(ItemRecord, item_id)
    if item is None or (item.deleted and not include_deleted):
        raise HTTPException(HTTPStatus.NOT_FOUND, "Item not found")
    return item


def find_cart(session: Session, cart_id: int) -> CartRecord:
    cart = Store.get_cart(session, cart_id)
    if cart is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Cart not found")
    return cart


def save_item(session: Session, item: ItemRecord, data: Item) -> Item:
    try:
        Store.update_item(session, item, data)
    except OverflowError as error:
        session.rollback()
        raise HTTPException(
            HTTPStatus.UNPROCESSABLE_ENTITY, "Cart price is too large"
        ) from error
    return data


@app.post("/cart", status_code=HTTPStatus.CREATED)
async def create_cart(response: Response, session: DatabaseSession) -> CartCreated:
    cart = CartRecord()
    session.add(cart)
    session.commit()
    response.headers["Location"] = f"/cart/{cart.id}"
    return CartCreated(id=cart.id)


@app.get("/cart/{cart_id}")
async def get_cart(cart_id: int, session: DatabaseSession) -> Cart:
    return Store.to_cart(find_cart(session, cart_id))


@app.get("/cart")
async def list_carts(
    session: DatabaseSession,
    offset: Offset = 0,
    limit: Limit = 10,
    min_price: PriceFilter = None,
    max_price: PriceFilter = None,
    min_quantity: QuantityFilter = None,
    max_quantity: QuantityFilter = None,
) -> list[Cart]:
    records = session.scalars(
        select(CartRecord).options(
            selectinload(CartRecord.lines).selectinload(CartLineRecord.item)
        )
    )
    carts = []
    for record in records:
        cart = Store.to_cart(record)
        quantity = sum(item.quantity for item in cart.items)
        if min_price is not None and cart.price < min_price:
            continue
        if max_price is not None and cart.price > max_price:
            continue
        if min_quantity is not None and quantity < min_quantity:
            continue
        if max_quantity is not None and quantity > max_quantity:
            continue
        carts.append(cart)
    return carts[offset : offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}")
async def add_to_cart(cart_id: int, item_id: int, session: DatabaseSession) -> Cart:
    cart = find_cart(session, cart_id)
    item = find_item(session, item_id)
    try:
        Store.add_to_cart(session, cart, item)
    except OverflowError as error:
        session.rollback()
        raise HTTPException(
            HTTPStatus.UNPROCESSABLE_ENTITY, "Cart price is too large"
        ) from error
    return Store.to_cart(find_cart(session, cart_id))


@app.post("/item", status_code=HTTPStatus.CREATED)
async def create_item(
    data: ItemData, response: Response, session: DatabaseSession
) -> Item:
    item = ItemRecord(**data.model_dump())
    session.add(item)
    session.commit()
    response.headers["Location"] = f"/item/{item.id}"
    return to_item(item)


@app.get("/item/{item_id}")
async def get_item(item_id: int, session: DatabaseSession) -> Item:
    return to_item(find_item(session, item_id))


@app.get("/item")
async def list_items(
    session: DatabaseSession,
    offset: Offset = 0,
    limit: Limit = 10,
    min_price: PriceFilter = None,
    max_price: PriceFilter = None,
    show_deleted: bool = False,
) -> list[Item]:
    statement = select(ItemRecord)
    if not show_deleted:
        statement = statement.where(ItemRecord.deleted.is_(False))
    if min_price is not None:
        statement = statement.where(ItemRecord.price >= min_price)
    if max_price is not None:
        statement = statement.where(ItemRecord.price <= max_price)
    items = session.scalars(statement.offset(offset).limit(limit))
    return [to_item(item) for item in items]


@app.put("/item/{item_id}")
async def replace_item(item_id: int, data: ItemData, session: DatabaseSession) -> Item:
    item = find_item(session, item_id, include_deleted=True)
    return save_item(session, item, Item(id=item_id, **data.model_dump()))


@app.patch("/item/{item_id}", response_model=Item)
async def patch_item(
    item_id: int, data: ItemPatch, session: DatabaseSession
) -> Item | Response:
    item = find_item(session, item_id, include_deleted=True)
    if item.deleted:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)
    updated = to_item(item).model_copy(update=data.model_dump(exclude_unset=True))
    return save_item(session, item, updated)


@app.delete("/item/{item_id}")
async def delete_item(item_id: int, session: DatabaseSession) -> Response:
    item = find_item(session, item_id, include_deleted=True)
    item.deleted = True
    session.commit()
    return Response(status_code=HTTPStatus.OK)
