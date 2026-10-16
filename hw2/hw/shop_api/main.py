from fastapi import Depends, FastAPI, HTTPException, Query, Response
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from shop_api.database import CartLine, CartRow, ItemRow, get_session
from pydantic import BaseModel, ConfigDict, Field, field_validator
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(title="Shop API")
Instrumentator(excluded_handlers=["/metrics"]).instrument(app).expose(
    app, include_in_schema=False
)


class ItemData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    price: float = Field(ge=0, allow_inf_nan=False)


class Item(ItemData):
    model_config = ConfigDict(from_attributes=True)

    id: int
    deleted: bool = False


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    price: float | None = Field(default=None, ge=0, allow_inf_nan=False)

    @field_validator("name", "price")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("Field cannot be null")
        return value


class CartItem(BaseModel):
    id: int
    name: str
    quantity: int
    available: bool


class Cart(BaseModel):
    id: int
    items: list[CartItem]
    price: float


def find_item(session: Session, item_id: int, include_deleted: bool = False) -> ItemRow:
    item = session.get(ItemRow, item_id)
    if item is None or (item.deleted and not include_deleted):
        raise HTTPException(status_code=404, detail="Item not found")
    return item


def find_cart(session: Session, cart_id: int) -> CartRow:
    cart = session.get(CartRow, cart_id)
    if cart is None:
        raise HTTPException(status_code=404, detail="Cart not found")
    return cart


def cart_response(cart: CartRow) -> Cart:
    return Cart(
        id=cart.id,
        items=[CartItem(id=line.item_id, name=line.item.name,
                        quantity=line.quantity, available=not line.item.deleted)
               for line in cart.lines],
        price=sum(line.item.price * line.quantity
                  for line in cart.lines if not line.item.deleted),
    )


@app.post("/item", status_code=201, response_model=Item)
def create_item(
    body: ItemData, response: Response,
    session: Session = Depends(get_session, scope="function"),
):
    item = ItemRow(**body.model_dump())
    session.add(item)
    session.flush()
    response.headers["Location"] = f"/item/{item.id}"
    return Item.model_validate(item)


@app.get("/item", response_model=list[Item])
def list_items(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, gt=0),
    min_price: float | None = Query(default=None, ge=0, allow_inf_nan=False),
    max_price: float | None = Query(default=None, ge=0, allow_inf_nan=False),
    show_deleted: bool = False,
    session: Session = Depends(get_session, scope="function"),
):
    query = select(ItemRow).order_by(ItemRow.id)
    if not show_deleted:
        query = query.where(ItemRow.deleted.is_(False))
    if min_price is not None:
        query = query.where(ItemRow.price >= min_price)
    if max_price is not None:
        query = query.where(ItemRow.price <= max_price)
    return [Item.model_validate(item) for item in session.scalars(query.offset(offset).limit(limit))]


@app.get("/item/{item_id}", response_model=Item)
def get_item(item_id: int, session: Session = Depends(get_session, scope="function")):
    return Item.model_validate(find_item(session, item_id))


@app.put("/item/{item_id}", response_model=Item)
def replace_item(
    item_id: int, body: ItemData,
    session: Session = Depends(get_session, scope="function"),
):
    item = find_item(session, item_id)
    item.name, item.price = body.name, body.price
    session.flush()
    return Item.model_validate(item)


@app.patch("/item/{item_id}", response_model=Item)
def patch_item(
    item_id: int, body: ItemPatch,
    session: Session = Depends(get_session, scope="function"),
):
    item = find_item(session, item_id, include_deleted=True)
    if item.deleted:
        return Response(status_code=304)
    for name, value in body.model_dump(exclude_unset=True).items():
        setattr(item, name, value)
    session.flush()
    return Item.model_validate(item)


@app.delete("/item/{item_id}", response_model=Item)
def delete_item(item_id: int, session: Session = Depends(get_session, scope="function")):
    item = find_item(session, item_id, include_deleted=True)
    item.deleted = True
    session.flush()
    return Item.model_validate(item)


@app.post("/cart", status_code=201)
def create_cart(
    response: Response,
    session: Session = Depends(get_session, scope="function"),
) -> dict[str, int]:
    cart = CartRow()
    session.add(cart)
    session.flush()
    response.headers["Location"] = f"/cart/{cart.id}"
    return {"id": cart.id}


@app.get("/cart", response_model=list[Cart])
def list_carts(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, gt=0),
    min_price: float | None = Query(default=None, ge=0, allow_inf_nan=False),
    max_price: float | None = Query(default=None, ge=0, allow_inf_nan=False),
    min_quantity: int | None = Query(default=None, ge=0),
    max_quantity: int | None = Query(default=None, ge=0),
    session: Session = Depends(get_session, scope="function"),
):
    price = func.coalesce(func.sum(case(
        (ItemRow.deleted.is_(False), ItemRow.price * CartLine.quantity), else_=0
    )), 0)
    quantity = func.coalesce(func.sum(CartLine.quantity), 0)
    totals = (select(CartRow.id.label("id"), price.label("price"), quantity.label("quantity"))
              .outerjoin(CartLine, CartRow.id == CartLine.cart_id)
              .outerjoin(ItemRow, CartLine.item_id == ItemRow.id)
              .group_by(CartRow.id).subquery())
    query = select(CartRow).join(totals, totals.c.id == CartRow.id)
    for column, lower, upper in ((totals.c.price, min_price, max_price),
                                 (totals.c.quantity, min_quantity, max_quantity)):
        if lower is not None:
            query = query.where(column >= lower)
        if upper is not None:
            query = query.where(column <= upper)
    query = (query.order_by(CartRow.id).offset(offset).limit(limit)
             .options(selectinload(CartRow.lines).joinedload(CartLine.item)))
    return [cart_response(cart) for cart in session.scalars(query)]


@app.get("/cart/{cart_id}", response_model=Cart)
def get_cart(cart_id: int, session: Session = Depends(get_session, scope="function")):
    return cart_response(find_cart(session, cart_id))


@app.post("/cart/{cart_id}/add/{item_id}", response_model=Cart)
def add_item(
    cart_id: int, item_id: int,
    session: Session = Depends(get_session, scope="function"),
):
    # Lock the cart so simultaneous requests do not lose quantity increments.
    cart = session.scalar(select(CartRow).where(CartRow.id == cart_id).with_for_update())
    if cart is None:
        raise HTTPException(status_code=404, detail="Cart not found")
    find_item(session, item_id)
    line = session.get(CartLine, (cart_id, item_id))
    if line is None:
        session.add(CartLine(cart_id=cart_id, item_id=item_id, quantity=1))
    else:
        line.quantity += 1
    session.flush()
    session.expire(cart, ["lines"])
    return cart_response(cart)
