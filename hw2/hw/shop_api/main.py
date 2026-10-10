from http import HTTPStatus
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, ConfigDict, NonNegativeFloat, NonNegativeInt, PositiveInt
from sqlalchemy import select
from sqlalchemy.orm import Session

from shop_api.chat import router as chat_router
from shop_api.db import CartItemOrm, CartOrm, ItemOrm, get_session

app = FastAPI(title="Shop API")
app.include_router(chat_router)
Instrumentator().instrument(app).expose(app)


class Item(BaseModel):
    id: int
    name: str
    price: float
    deleted: bool = False


class ItemRequest(BaseModel):
    name: str
    price: NonNegativeFloat


class PatchItemRequest(BaseModel):
    # deleted veya baska alan gelirse 422
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    price: NonNegativeFloat | None = None


class CartItem(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class Cart(BaseModel):
    id: int
    items: list[CartItem]
    price: float


SessionDep = Annotated[Session, Depends(get_session)]


def to_item(item: ItemOrm) -> Item:
    return Item(id=item.id, name=item.name, price=item.price, deleted=item.deleted)


def get_item_or_404(session: Session, item_id: int) -> ItemOrm:
    item = session.get(ItemOrm, item_id)
    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} not found")
    return item


def get_cart_or_404(session: Session, cart_id: int) -> CartOrm:
    cart = session.get(CartOrm, cart_id)
    if cart is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Cart {cart_id} not found")
    return cart


@app.post("/item", status_code=HTTPStatus.CREATED)
def create_item(body: ItemRequest, response: Response, session: SessionDep) -> Item:
    item = ItemOrm(name=body.name, price=body.price, deleted=False)
    session.add(item)
    session.commit()
    response.headers["location"] = f"/item/{item.id}"
    return to_item(item)


@app.get("/item/{item_id}")
def get_item(item_id: int, session: SessionDep) -> Item:
    return to_item(get_item_or_404(session, item_id))


@app.get("/item")
def get_items(
    session: SessionDep,
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    show_deleted: bool = False,
) -> list[Item]:
    query = select(ItemOrm).order_by(ItemOrm.id)
    if not show_deleted:
        query = query.where(ItemOrm.deleted.is_(False))
    if min_price is not None:
        query = query.where(ItemOrm.price >= min_price)
    if max_price is not None:
        query = query.where(ItemOrm.price <= max_price)
    return [to_item(item) for item in session.scalars(query.offset(offset).limit(limit))]


@app.put("/item/{item_id}")
def replace_item(item_id: int, body: ItemRequest, session: SessionDep) -> Item:
    item = get_item_or_404(session, item_id)
    item.name = body.name
    item.price = body.price
    session.commit()
    return to_item(item)


@app.patch("/item/{item_id}")
def update_item(item_id: int, body: PatchItemRequest, session: SessionDep) -> Item:
    item = session.get(ItemOrm, item_id)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} not found")
    if item.deleted:
        # 304 body olmadan donmeli
        return Response(status_code=HTTPStatus.NOT_MODIFIED)

    if body.name is not None:
        item.name = body.name
    if body.price is not None:
        item.price = body.price
    session.commit()
    return to_item(item)


@app.delete("/item/{item_id}")
def delete_item(item_id: int, session: SessionDep) -> Item:
    item = session.get(ItemOrm, item_id)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} not found")
    # gercekten silmiyoruz, sadece isaretliyoruz
    item.deleted = True
    session.commit()
    return to_item(item)


def build_cart(cart: CartOrm) -> Cart:
    cart_items = []
    price = 0.0
    for cart_item in cart.items:
        item = cart_item.item
        cart_items.append(
            CartItem(
                id=item.id,
                name=item.name,
                quantity=cart_item.quantity,
                available=not item.deleted,
            )
        )
        # silinen urun fiyata eklenmesin
        if not item.deleted:
            price += item.price * cart_item.quantity
    return Cart(id=cart.id, items=cart_items, price=price)


@app.post("/cart", status_code=HTTPStatus.CREATED)
def create_cart(response: Response, session: SessionDep) -> dict[str, int]:
    cart = CartOrm()
    session.add(cart)
    session.commit()
    response.headers["location"] = f"/cart/{cart.id}"
    return {"id": cart.id}


@app.get("/cart/{cart_id}")
def get_cart(cart_id: int, session: SessionDep) -> Cart:
    return build_cart(get_cart_or_404(session, cart_id))


@app.get("/cart")
def get_carts(
    session: SessionDep,
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    min_quantity: Annotated[NonNegativeInt | None, Query()] = None,
    max_quantity: Annotated[NonNegativeInt | None, Query()] = None,
) -> list[Cart]:
    result = []
    for cart_orm in session.scalars(select(CartOrm).order_by(CartOrm.id)):
        cart = build_cart(cart_orm)
        quantity = sum(item.quantity for item in cart.items)
        if min_price is not None and cart.price < min_price:
            continue
        if max_price is not None and cart.price > max_price:
            continue
        if min_quantity is not None and quantity < min_quantity:
            continue
        if max_quantity is not None and quantity > max_quantity:
            continue
        result.append(cart)
    return result[offset : offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}")
def add_to_cart(cart_id: int, item_id: int, session: SessionDep) -> Cart:
    cart = get_cart_or_404(session, cart_id)
    get_item_or_404(session, item_id)

    cart_item = session.get(CartItemOrm, (cart_id, item_id))
    if cart_item is None:
        session.add(CartItemOrm(cart_id=cart_id, item_id=item_id, quantity=1))
    else:
        # +1'i veritabani yapsin, ayni anda gelen isteklerde kayip olmasin
        cart_item.quantity = CartItemOrm.quantity + 1
    session.commit()
    return build_cart(cart)
