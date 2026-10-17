"""API интернет-магазина из ДЗ2 с хранением данных в PostgreSQL через SQLAlchemy."""

from __future__ import annotations

from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, NonNegativeFloat, NonNegativeInt, PositiveInt
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .database import Cart, CartLine, Item, create_tables, get_session


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield


app = FastAPI(title="Shop API", lifespan=lifespan)
SessionDep = Annotated[Session, Depends(get_session)]


class ItemResponse(BaseModel):
    id: int
    name: str
    price: float
    deleted: bool

    @classmethod
    def from_entity(cls, item: Item) -> ItemResponse:
        return cls(id=item.id, name=item.name, price=item.price, deleted=item.deleted)


class ItemCreateRequest(BaseModel):
    name: str
    price: float


class ItemPutRequest(BaseModel):
    name: str
    price: float


class ItemPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    price: float | None = None


class CartItemResponse(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class CartResponse(BaseModel):
    id: int
    items: list[CartItemResponse]
    price: float

    @classmethod
    def from_entity(cls, cart: Cart) -> CartResponse:
        items = []
        price = 0.0
        for line in sorted(cart.lines, key=lambda line: line.item_id):
            item = line.item
            items.append(
                CartItemResponse(
                    id=item.id,
                    name=item.name,
                    quantity=line.quantity,
                    available=not item.deleted,
                )
            )
            price += item.price * line.quantity
        return cls(id=cart.id, items=items, price=price)


def load_cart(session: Session, cart_id: int) -> Cart | None:
    return session.scalar(
        select(Cart)
        .options(selectinload(Cart.lines).joinedload(CartLine.item))
        .where(Cart.id == cart_id)
    )


@app.post("/cart", status_code=HTTPStatus.CREATED)
def post_cart(session: SessionDep, response: Response) -> dict[str, int]:
    cart = Cart()
    session.add(cart)
    session.commit()
    session.refresh(cart)
    response.headers["location"] = f"/cart/{cart.id}"
    return {"id": cart.id}


@app.get("/cart/{id}")
def get_cart(id: int, session: SessionDep) -> CartResponse:
    cart = load_cart(session, id)
    if cart is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Корзина {id} не найдена")
    return CartResponse.from_entity(cart)


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
    carts = session.scalars(
        select(Cart)
        .options(selectinload(Cart.lines).joinedload(CartLine.item))
        .order_by(Cart.id)
    ).all()
    result: list[CartResponse] = []
    for cart in carts:
        response = CartResponse.from_entity(cart)
        quantity = sum(line.quantity for line in cart.lines)
        if min_price is not None and response.price < min_price:
            continue
        if max_price is not None and response.price > max_price:
            continue
        if min_quantity is not None and quantity < min_quantity:
            continue
        if max_quantity is not None and quantity > max_quantity:
            continue
        result.append(response)
    return result[offset : offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}")
def add_item_to_cart(cart_id: int, item_id: int, session: SessionDep) -> CartResponse:
    # Lock the cart to serialize concurrent additions to the same cart.
    cart = session.scalar(select(Cart).where(Cart.id == cart_id).with_for_update())
    if cart is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Корзина {cart_id} не найдена")
    item = session.get(Item, item_id)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Товар {item_id} не найден")

    line = session.get(CartLine, (cart_id, item_id))
    if line is None:
        session.add(CartLine(cart_id=cart_id, item_id=item_id, quantity=1))
    else:
        line.quantity += 1
    session.commit()
    session.expire_all()
    refreshed = load_cart(session, cart_id)
    assert refreshed is not None
    return CartResponse.from_entity(refreshed)


@app.post("/item", status_code=HTTPStatus.CREATED)
def post_item(info: ItemCreateRequest, session: SessionDep, response: Response) -> ItemResponse:
    item = Item(name=info.name, price=info.price)
    session.add(item)
    session.commit()
    session.refresh(item)
    response.headers["location"] = f"/item/{item.id}"
    return ItemResponse.from_entity(item)


@app.get("/item/{id}")
def get_item(id: int, session: SessionDep) -> ItemResponse:
    item = session.get(Item, id)
    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Товар {id} не найден")
    return ItemResponse.from_entity(item)


@app.get("/item")
def get_item_list(
    session: SessionDep,
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    show_deleted: Annotated[bool, Query()] = False,
) -> list[ItemResponse]:
    stmt = select(Item)
    if not show_deleted:
        stmt = stmt.where(Item.deleted.is_(False))
    if min_price is not None:
        stmt = stmt.where(Item.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Item.price <= max_price)
    stmt = stmt.order_by(Item.id).offset(offset).limit(limit)
    return [ItemResponse.from_entity(i) for i in session.scalars(stmt)]


@app.put("/item/{id}")
def put_item(id: int, info: ItemPutRequest, session: SessionDep) -> ItemResponse:
    item = session.get(Item, id)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_MODIFIED, f"Товар {id} не найден")
    item.name = info.name
    item.price = info.price
    session.commit()
    return ItemResponse.from_entity(item)


@app.patch("/item/{id}")
def patch_item(id: int, info: ItemPatchRequest, session: SessionDep) -> ItemResponse:
    item = session.get(Item, id)
    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_MODIFIED, f"Товар {id} не найден")
    if info.name is not None:
        item.name = info.name
    if info.price is not None:
        item.price = info.price
    session.commit()
    return ItemResponse.from_entity(item)


@app.delete("/item/{id}")
def delete_item(id: int, session: SessionDep) -> Response:
    item = session.get(Item, id)
    if item is not None:
        item.deleted = True
        session.commit()
    return Response("")
