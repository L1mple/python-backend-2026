from collections.abc import Iterable
from http import HTTPStatus
from typing import Annotated, Protocol

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from shop_api.db import CartItemOrm, CartOrm, ItemOrm, get_session


class Item(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    price: float = Field(ge=0)
    deleted: bool = False


class CartItem(BaseModel):
    id: int
    name: str
    quantity: int = Field(gt=0)
    available: bool = True


class Cart(BaseModel):
    id: int
    items: list[CartItem]
    price: float = Field(ge=0)

    @property
    def quantity(self) -> int:
        return sum(item.quantity for item in self.items)

    @classmethod
    def from_orm_cart(cls, cart: CartOrm) -> "Cart":
        return cls(
            id=cart.id,
            items=[
                CartItem(
                    id=ci.item_id,
                    name=ci.item.name,
                    quantity=ci.quantity,
                    available=not ci.item.deleted,
                )
                for ci in cart.items
            ],
            price=sum(
                ci.item.price * ci.quantity for ci in cart.items if not ci.item.deleted
            ),
        )


class ItemClient(BaseModel):
    name: str
    price: float = Field(ge=0)


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    price: float | None = Field(None, ge=0)


class ListParams(BaseModel):
    offset: int = Field(0, ge=0)
    limit: int = Field(10, gt=0)
    min_price: float | None = Field(None, ge=0)
    max_price: float | None = Field(None, ge=0)


class CartListParams(ListParams):
    min_quantity: int | None = Field(None, ge=0)
    max_quantity: int | None = Field(None, ge=0)


class ItemListParams(ListParams):
    show_deleted: bool = False


class HasPrice(Protocol):
    price: float


def apply_list_params[T: HasPrice](objs: Iterable[T], params: ListParams) -> list[T]:
    filtered = [
        o
        for o in objs
        if (params.min_price is None or o.price >= params.min_price)
        and (params.max_price is None or o.price <= params.max_price)
    ]
    return filtered[params.offset : params.offset + params.limit]


SessionDep = Annotated[Session, Depends(get_session)]

app = FastAPI(title="Shop API")
Instrumentator().instrument(app).expose(app)


def get_item_or_404(session: Session, id: int) -> ItemOrm:
    item = session.get(ItemOrm, id)
    if item is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)
    return item


def get_cart_or_404(session: Session, id: int) -> CartOrm:
    cart = session.get(CartOrm, id)
    if cart is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)
    return cart


@app.post("/cart", status_code=HTTPStatus.CREATED)
def post_cart(response: Response, session: SessionDep) -> Cart:
    cart = CartOrm()
    session.add(cart)
    session.commit()
    response.headers["Location"] = f"/cart/{cart.id}"
    return Cart.from_orm_cart(cart)


@app.get("/cart/{id}", status_code=HTTPStatus.OK)
def get_cart(id: int, session: SessionDep) -> Cart:
    return Cart.from_orm_cart(get_cart_or_404(session, id))


@app.get("/cart")
def get_cart_list(
    params: Annotated[CartListParams, Query()],
    session: SessionDep,
) -> list[Cart]:
    carts = [
        Cart.from_orm_cart(c)
        for c in session.scalars(select(CartOrm).order_by(CartOrm.id))
    ]
    result = [
        c
        for c in carts
        if (params.min_quantity is None or c.quantity >= params.min_quantity)
        and (params.max_quantity is None or c.quantity <= params.max_quantity)
    ]
    return apply_list_params(result, params)


@app.post("/cart/{cart_id}/add/{item_id}")
def add_to_cart(cart_id: int, item_id: int, session: SessionDep):
    get_cart_or_404(session, cart_id)
    get_item_or_404(session, item_id)

    cart_item = session.get(CartItemOrm, (cart_id, item_id))
    if cart_item is None:
        session.add(CartItemOrm(cart_id=cart_id, item_id=item_id, quantity=1))
    else:
        cart_item.quantity += 1
    session.commit()


@app.post("/item", status_code=HTTPStatus.CREATED)
def post_item(item: ItemClient, session: SessionDep) -> Item:
    orm_item = ItemOrm(name=item.name, price=item.price)
    session.add(orm_item)
    session.commit()
    return Item.model_validate(orm_item)


@app.get("/item/{id}", status_code=HTTPStatus.OK)
def get_item(id: int, session: SessionDep) -> Item:
    item = get_item_or_404(session, id)
    if item.deleted:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)
    return Item.model_validate(item)


@app.get("/item")
def get_item_list(
    params: Annotated[ItemListParams, Query()], session: SessionDep
) -> list[Item]:
    query = select(ItemOrm).order_by(ItemOrm.id)
    if not params.show_deleted:
        query = query.where(ItemOrm.deleted.is_(False))
    if params.min_price is not None:
        query = query.where(ItemOrm.price >= params.min_price)
    if params.max_price is not None:
        query = query.where(ItemOrm.price <= params.max_price)
    query = query.offset(params.offset).limit(params.limit)
    return [Item.model_validate(i) for i in session.scalars(query)]


@app.put("/item/{id}", status_code=HTTPStatus.OK)
def put_item(id: int, body: ItemClient, session: SessionDep) -> Item:
    item = get_item_or_404(session, id)
    item.name = body.name
    item.price = body.price
    session.commit()
    return Item.model_validate(item)


@app.patch("/item/{id}", status_code=HTTPStatus.OK)
def patch_item(id: int, body: ItemPatch, session: SessionDep):
    item = get_item_or_404(session, id)
    if item.deleted:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(item, field, value)
    session.commit()
    return Item.model_validate(item)


@app.delete("/item/{id}", status_code=HTTPStatus.OK)
def delete_item(id: int, session: SessionDep):
    item = get_item_or_404(session, id)
    item.deleted = True
    session.commit()
