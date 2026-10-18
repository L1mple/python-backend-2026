from http import HTTPStatus
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .database import Cart, CartItem, Item, get_session, lifespan

app = FastAPI(title="Shop API", lifespan=lifespan)
SessionDep = Annotated[Session, Depends(get_session)]


class ItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    price: float = Field(ge=0)


class ItemReplace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    price: float = Field(ge=0)


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    price: float | None = Field(default=None, ge=0)


def item_view(item: Item) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "price": item.price,
        "deleted": item.deleted,
    }


def cart_view(cart_id: int, session: Session) -> dict:
    cart_items = []
    total_price = 0.0

    rows = session.execute(
        select(Item, CartItem.quantity).join(CartItem, CartItem.item_id == Item.id)
        .where(CartItem.cart_id == cart_id).order_by(Item.id)
    )
    for item, quantity in rows:
        available = not item.deleted

        cart_items.append(
            {
                "id": item.id,
                "name": item.name,
                "quantity": quantity,
                "available": available,
            }
        )

        if available:
            total_price += item.price * quantity

    return {
        "id": cart_id,
        "items": cart_items,
        "price": total_price,
    }


@app.post("/cart", status_code=HTTPStatus.CREATED)
def create_cart(response: Response, session: SessionDep) -> dict[str, int]:
    cart = Cart()
    session.add(cart)
    session.flush()
    response.headers["Location"] = f"/cart/{cart.id}"

    return {"id": cart.id}


@app.get("/cart/{cart_id}")
def get_cart(cart_id: int, session: SessionDep) -> dict:
    if session.get(Cart, cart_id) is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)

    return cart_view(cart_id, session)


@app.get("/cart")
def get_carts(
    session: SessionDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    min_quantity: Annotated[int | None, Query(ge=0)] = None,
    max_quantity: Annotated[int | None, Query(ge=0)] = None,
) -> list[dict]:
    result = []

    for cart_id in session.scalars(select(Cart.id).order_by(Cart.id)):
        cart = cart_view(cart_id, session)

        quantity = sum(
            item["quantity"]
            for item in cart["items"]
        )

        if min_price is not None and cart["price"] < min_price:
            continue

        if max_price is not None and cart["price"] > max_price:
            continue

        if min_quantity is not None and quantity < min_quantity:
            continue

        if max_quantity is not None and quantity > max_quantity:
            continue

        result.append(cart)

    return result[offset : offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}")
def add_item_to_cart(cart_id: int, item_id: int, session: SessionDep) -> dict:
    cart = session.scalar(select(Cart).where(Cart.id == cart_id).with_for_update())
    if cart is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)

    item = session.scalar(select(Item).where(Item.id == item_id).with_for_update())
    if item is None or item.deleted:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)

    statement = insert(CartItem).values(cart_id=cart_id, item_id=item_id, quantity=1)
    session.execute(statement.on_conflict_do_update(
        index_elements=[CartItem.cart_id, CartItem.item_id],
        set_={"quantity": CartItem.quantity + 1},
    ))
    return cart_view(cart_id, session)


@app.post("/item", status_code=HTTPStatus.CREATED)
def create_item(body: ItemCreate, response: Response, session: SessionDep) -> dict:
    item = Item(name=body.name, price=body.price)
    session.add(item)
    session.flush()
    response.headers["Location"] = f"/item/{item.id}"

    return item_view(item)


@app.get("/item/{item_id}")
def get_item(item_id: int, session: SessionDep) -> dict:
    item = session.get(Item, item_id)

    if item is None or item.deleted:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)

    return item_view(item)


@app.get("/item")
def get_items(
    session: SessionDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    show_deleted: bool = False,
) -> list[dict]:
    query = select(Item).order_by(Item.id)

    if not show_deleted:
        query = query.where(Item.deleted.is_(False))

    if min_price is not None:
        query = query.where(Item.price >= min_price)

    if max_price is not None:
        query = query.where(Item.price <= max_price)

    return [item_view(item) for item in session.scalars(query.offset(offset).limit(limit))]


@app.put("/item/{item_id}")
def replace_item(item_id: int, body: ItemReplace, session: SessionDep):
    item = session.scalar(select(Item).where(Item.id == item_id).with_for_update())

    if item is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)

    if item.deleted:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)
    item.name = body.name
    item.price = body.price
    session.flush()

    return item_view(item)


@app.patch("/item/{item_id}")
def patch_item(item_id: int, body: ItemPatch, session: SessionDep):
    item = session.scalar(select(Item).where(Item.id == item_id).with_for_update())

    if item is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)

    if item.deleted:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)

    changes = body.model_dump(exclude_unset=True)
    if any(value is None for value in changes.values()):
        raise HTTPException(status_code=HTTPStatus.UNPROCESSABLE_ENTITY, detail="Fields cannot be null")

    for key, value in changes.items():
        setattr(item, key, value)
    session.flush()

    return item_view(item)


@app.delete("/item/{item_id}")
def delete_item(item_id: int, session: SessionDep) -> dict:
    item = session.scalar(select(Item).where(Item.id == item_id).with_for_update())

    if item is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)
    item.deleted = True
    session.flush()

    return item_view(item)
