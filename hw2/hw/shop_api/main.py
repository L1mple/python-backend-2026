from collections.abc import Generator
from http import HTTPStatus

from fastapi import Depends, FastAPI, HTTPException, Response
from pydantic import (
    BaseModel,
    ConfigDict,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveInt,
)
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import Boolean, Float, ForeignKey, Integer, Unicode, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from shop_api.database import make_database_url


class Base(DeclarativeBase):
    pass


class ItemModel(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Unicode)
    price: Mapped[float] = mapped_column(Float)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class CartModel(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)


class CartItemModel(Base):
    __tablename__ = "cart_items"

    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id"), primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer)


database_url = make_database_url()
connect_args = {"check_same_thread": False} if str(database_url).startswith("sqlite") else {}
engine = create_engine(database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(engine)

app = FastAPI(title="Shop API")
Instrumentator().instrument(app).expose(app)


class ItemCreate(BaseModel):
    name: str
    price: NonNegativeFloat


class ItemPatch(BaseModel):
    name: str | None = None
    price: NonNegativeFloat | None = None

    model_config = ConfigDict(extra="forbid")


Item = dict[str, int | str | float | bool]


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def item_data(item: ItemModel) -> Item:
    return {
        "id": item.id,
        "name": item.name,
        "price": item.price,
        "deleted": item.deleted,
    }


def cart_data(session: Session, cart: CartModel) -> dict[str, object]:
    rows = session.execute(
        select(CartItemModel, ItemModel)
        .join(ItemModel, CartItemModel.item_id == ItemModel.id)
        .where(CartItemModel.cart_id == cart.id)
        .order_by(CartItemModel.item_id)
    ).all()
    cart_items = []
    price = 0.0

    for cart_item, item in rows:
        cart_items.append(
            {
                "id": item.id,
                "name": item.name,
                "quantity": cart_item.quantity,
                "available": not item.deleted,
            }
        )
        price += item.price * cart_item.quantity

    return {"id": cart.id, "items": cart_items, "price": price}


@app.post("/item", status_code=HTTPStatus.CREATED)
def create_item(
    item: ItemCreate,
    response: Response,
    session: Session = Depends(get_session),
) -> Item:
    data = ItemModel(name=item.name, price=item.price, deleted=False)
    session.add(data)
    session.commit()
    session.refresh(data)
    response.headers["location"] = f"/item/{data.id}"
    return item_data(data)


@app.post("/cart", status_code=HTTPStatus.CREATED)
def create_cart(
    response: Response,
    session: Session = Depends(get_session),
) -> dict[str, int]:
    cart = CartModel()
    session.add(cart)
    session.commit()
    session.refresh(cart)
    response.headers["location"] = f"/cart/{cart.id}"
    return {"id": cart.id}


@app.get("/cart")
def get_carts(
    offset: NonNegativeInt = 0,
    limit: PositiveInt = 10,
    min_price: NonNegativeFloat | None = None,
    max_price: NonNegativeFloat | None = None,
    min_quantity: NonNegativeInt | None = None,
    max_quantity: NonNegativeInt | None = None,
    session: Session = Depends(get_session),
) -> list[dict[str, object]]:
    result = []
    carts = session.scalars(select(CartModel).order_by(CartModel.id)).all()
    for cart in carts:
        data = cart_data(session, cart)
        price = data["price"]
        quantity = sum(item["quantity"] for item in data["items"])
        if min_price is not None and price < min_price:
            continue
        if max_price is not None and price > max_price:
            continue
        if min_quantity is not None and quantity < min_quantity:
            continue
        if max_quantity is not None and quantity > max_quantity:
            continue
        result.append(data)

    return result[offset : offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}")
def add_item_to_cart(
    cart_id: int,
    item_id: int,
    session: Session = Depends(get_session),
) -> Response:
    cart = session.get(CartModel, cart_id)
    item = session.get(ItemModel, item_id)
    if cart is None or item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND)

    cart_item = session.get(CartItemModel, (cart_id, item_id))
    if cart_item is None:
        session.add(CartItemModel(cart_id=cart_id, item_id=item_id, quantity=1))
    else:
        cart_item.quantity += 1
    session.commit()
    return Response(status_code=HTTPStatus.OK)


@app.get("/cart/{cart_id}")
def get_cart(
    cart_id: int,
    session: Session = Depends(get_session),
) -> dict[str, object]:
    cart = session.get(CartModel, cart_id)
    if cart is None:
        raise HTTPException(HTTPStatus.NOT_FOUND)

    return cart_data(session, cart)


@app.get("/item")
def get_items(
    offset: NonNegativeInt = 0,
    limit: PositiveInt = 10,
    min_price: NonNegativeFloat | None = None,
    max_price: NonNegativeFloat | None = None,
    show_deleted: bool = False,
    session: Session = Depends(get_session),
) -> list[Item]:
    statement = select(ItemModel).order_by(ItemModel.id)
    if not show_deleted:
        statement = statement.where(~ItemModel.deleted)
    if min_price is not None:
        statement = statement.where(ItemModel.price >= min_price)
    if max_price is not None:
        statement = statement.where(ItemModel.price <= max_price)
    result = [item_data(item) for item in session.scalars(statement)]
    return result[offset : offset + limit]


@app.get("/item/{item_id}")
def get_item(
    item_id: int,
    session: Session = Depends(get_session),
) -> Item:
    item = session.get(ItemModel, item_id)
    if item is None or item.deleted:
        raise HTTPException(HTTPStatus.NOT_FOUND)

    return item_data(item)


@app.put("/item/{item_id}")
def replace_item(
    item_id: int,
    update: ItemCreate,
    session: Session = Depends(get_session),
) -> Item:
    item = session.get(ItemModel, item_id)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND)
    if item.deleted:
        raise HTTPException(HTTPStatus.NOT_MODIFIED)

    item.name = update.name
    item.price = update.price
    session.commit()
    session.refresh(item)
    return item_data(item)


@app.patch("/item/{item_id}")
def patch_item(
    item_id: int,
    update: ItemPatch,
    session: Session = Depends(get_session),
) -> Item:
    item = session.get(ItemModel, item_id)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND)
    if item.deleted:
        raise HTTPException(HTTPStatus.NOT_MODIFIED)

    values = update.model_dump(exclude_none=True)
    if "name" in values:
        item.name = values["name"]
    if "price" in values:
        item.price = values["price"]
    session.commit()
    session.refresh(item)
    return item_data(item)


@app.delete("/item/{item_id}")
def delete_item(
    item_id: int,
    session: Session = Depends(get_session),
) -> Response:
    item = session.get(ItemModel, item_id)
    if item is None:
        raise HTTPException(HTTPStatus.NOT_FOUND)

    item.deleted = True
    session.commit()
    return Response(status_code=HTTPStatus.OK)
