from contextlib import asynccontextmanager
from decimal import Decimal
from http import HTTPStatus
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import engine, get_db
from models import Base, Item, Cart, CartItem


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Shop API", lifespan=lifespan)
Instrumentator().instrument(app).expose(app)


class ItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    price: Annotated[float, Field(ge=0)]


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    price: Annotated[float | None, Field(ge=0)] = None


def item_response(item: Item) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "price": float(item.price),
        "deleted": item.deleted,
    }


def require_item(db: Session, item_id: int) -> Item:
    item = db.get(Item, item_id)
    if item is None or item.deleted:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Item not found",
        )
    return item


def require_cart(db: Session, cart_id: int) -> Cart:
    cart = db.get(Cart, cart_id)
    if cart is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Cart not found",
        )
    return cart


def make_cart_response(db: Session, cart_id: int) -> dict:
    rows = db.execute(
        select(CartItem, Item)
        .join(Item, CartItem.item_id == Item.id)
        .where(CartItem.cart_id == cart_id)
        .order_by(CartItem.item_id)
    ).all()

    cart_items = []
    total_price = 0.0

    for cart_item, item in rows:
        cart_items.append({
            "id": item.id,
            "name": item.name,
            "quantity": cart_item.quantity,
            "available": not item.deleted,
        })
        total_price += float(item.price) * cart_item.quantity

    return {
        "id": cart_id,
        "items": cart_items,
        "price": total_price,
    }

@app.post("/cart", status_code=HTTPStatus.CREATED)
def create_cart(
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    cart = Cart()
    db.add(cart)
    db.commit()
    db.refresh(cart)

    response.headers["Location"] = f"/cart/{cart.id}"
    return {"id": cart.id}


@app.get("/cart/{cart_id}")
def get_cart(
    cart_id: int,
    db: Session = Depends(get_db),
) -> dict:
    require_cart(db, cart_id)
    return make_cart_response(db, cart_id)


@app.get("/cart")
def get_carts(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    min_quantity: Annotated[int | None, Query(ge=0)] = None,
    max_quantity: Annotated[int | None, Query(ge=0)] = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    result = []

    carts = db.scalars(select(Cart).order_by(Cart.id)).all()

    for cart in carts:
        data = make_cart_response(db, cart.id)
        quantity = sum(item["quantity"] for item in data["items"])

        if min_price is not None and data["price"] < min_price:
            continue
        if max_price is not None and data["price"] > max_price:
            continue
        if min_quantity is not None and quantity < min_quantity:
            continue
        if max_quantity is not None and quantity > max_quantity:
            continue

        result.append(data)

    return result[offset:offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}")
def add_item_to_cart(
    cart_id: int,
    item_id: int,
    db: Session = Depends(get_db),
) -> dict:
    cart = db.scalar(
        select(Cart)
        .where(Cart.id == cart_id)
        .with_for_update()
    )

    if cart is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Cart not found",
        )

    require_item(db, item_id)

    cart_item = db.get(CartItem, (cart_id, item_id))

    if cart_item is None:
        db.add(CartItem(
            cart_id=cart_id,
            item_id=item_id,
            quantity=1,
        ))
    else:
        cart_item.quantity += 1

    db.flush()
    result = make_cart_response(db, cart_id)
    db.commit()

    return result

@app.post("/item", status_code=HTTPStatus.CREATED)
def create_item(
    item: ItemCreate,
    db: Session = Depends(get_db),
) -> dict:
    new_item = Item(
        name=item.name,
        price=Decimal(str(item.price)),
        deleted=False,
    )

    db.add(new_item)
    db.commit()
    db.refresh(new_item)

    return item_response(new_item)


@app.get("/item/{item_id}")
def get_item(
    item_id: int,
    db: Session = Depends(get_db),
) -> dict:
    return item_response(require_item(db, item_id))


@app.get("/item")
def get_items(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(gt=0)] = 10,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    show_deleted: bool = False,
    db: Session = Depends(get_db),
) -> list[dict]:
    stmt = select(Item)

    if not show_deleted:
        stmt = stmt.where(Item.deleted.is_(False))

    if min_price is not None:
        stmt = stmt.where(Item.price >= Decimal(str(min_price)))

    if max_price is not None:
        stmt = stmt.where(Item.price <= Decimal(str(max_price)))

    stmt = stmt.order_by(Item.id).offset(offset).limit(limit)

    return [item_response(i) for i in db.scalars(stmt)]


@app.put("/item/{item_id}")
def replace_item(
    item_id: int,
    item: ItemCreate,
    db: Session = Depends(get_db),
) -> dict:
    obj = require_item(db, item_id)

    obj.name = item.name
    obj.price = Decimal(str(item.price))

    db.commit()
    return item_response(obj)


@app.patch("/item/{item_id}")
def patch_item(
    item_id: int,
    patch: ItemPatch,
    db: Session = Depends(get_db),
):
    obj = db.get(Item, item_id)

    if obj is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Item not found",
        )

    if obj.deleted:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)

    changes = patch.model_dump(exclude_unset=True)

    for field, value in changes.items():
        if value is None:
            raise HTTPException(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                detail=f"{field} cannot be null",
            )
        if field == "price":
            value = Decimal(str(value))
        setattr(obj, field, value)

    db.commit()
    return item_response(obj)


@app.delete("/item/{item_id}")
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
) -> dict:
    obj = db.get(Item, item_id)

    if obj is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Item not found",
        )

    obj.deleted = True
    db.commit()

    return item_response(obj)
