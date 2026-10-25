from collections.abc import Iterator
from http import HTTPStatus
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from sqlalchemy import case, func, select, update
from sqlalchemy.orm import Session, selectinload, sessionmaker

from .database import CartItemRecord, CartRecord, ItemRecord, create_database
from .models import Cart, CartCreated, CartItem, Item, ItemData, ItemPatch


def _get_item(
    session: Session,
    item_id: int,
    *,
    include_deleted: bool = False,
    lock: bool = False,
) -> ItemRecord:
    query = select(ItemRecord).where(ItemRecord.id == item_id)
    if lock:
        query = query.with_for_update()
    item = session.scalar(query)
    if item is None or (item.deleted and not include_deleted):
        raise HTTPException(HTTPStatus.NOT_FOUND, "Item not found")
    return item


def _get_cart(session: Session, cart_id: int, *, lock: bool = False) -> CartRecord:
    query = select(CartRecord).where(CartRecord.id == cart_id)
    if lock:
        query = query.with_for_update()
    cart = session.scalar(query)
    if cart is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Cart not found")
    return cart


def _cart_view(cart: CartRecord) -> Cart:
    return Cart(
        id=cart.id,
        items=[
            CartItem(
                id=position.item_id,
                name=position.item.name,
                quantity=position.quantity,
                available=not position.item.deleted,
            )
            for position in cart.items
        ],
        price=sum(
            position.item.price * position.quantity
            for position in cart.items
            if not position.item.deleted
        ),
    )


def create_app(database_url: str | None = None) -> FastAPI:
    app = FastAPI(title="Shop API")
    engine = create_database(database_url)
    session_factory = sessionmaker(engine, expire_on_commit=False)
    app.state.engine = engine
    app.state.session_factory = session_factory

    def get_session(request: Request) -> Iterator[Session]:
        with session_factory() as session:
            try:
                if engine.dialect.name == "sqlite" and request.method in {
                    "POST", "PUT", "PATCH", "DELETE"
                }:
                    session.connection(execution_options={"write_transaction": True})
                yield session
            except Exception:
                session.rollback()
                raise

    DatabaseSession = Annotated[Session, Depends(get_session)]

    @app.post("/cart", status_code=HTTPStatus.CREATED)
    def create_cart(response: Response, session: DatabaseSession) -> CartCreated:
        cart = CartRecord()
        session.add(cart)
        session.flush()
        session.commit()
        response.headers["Location"] = f"/cart/{cart.id}"
        return CartCreated(id=cart.id)

    @app.get("/cart")
    def list_carts(
        session: DatabaseSession,
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(gt=0)] = 10,
        min_price: Annotated[float | None, Query(ge=0, allow_inf_nan=False)] = None,
        max_price: Annotated[float | None, Query(ge=0, allow_inf_nan=False)] = None,
        min_quantity: Annotated[int | None, Query(ge=0)] = None,
        max_quantity: Annotated[int | None, Query(ge=0)] = None,
    ) -> list[Cart]:
        totals = (
            select(
                CartItemRecord.cart_id,
                func.sum(CartItemRecord.quantity).label("quantity"),
                func.sum(
                    case(
                        (ItemRecord.deleted.is_(False), ItemRecord.price * CartItemRecord.quantity),
                        else_=0.0,
                    )
                ).label("price"),
            )
            .join(ItemRecord, ItemRecord.id == CartItemRecord.item_id)
            .group_by(CartItemRecord.cart_id)
            .subquery()
        )
        query = select(CartRecord).outerjoin(totals, totals.c.cart_id == CartRecord.id)
        price = func.coalesce(totals.c.price, 0.0)
        quantity = func.coalesce(totals.c.quantity, 0)
        if min_price is not None:
            query = query.where(price >= min_price)
        if max_price is not None:
            query = query.where(price <= max_price)
        if min_quantity is not None:
            query = query.where(quantity >= min_quantity)
        if max_quantity is not None:
            query = query.where(quantity <= max_quantity)
        query = (
            query.options(selectinload(CartRecord.items))
            .order_by(CartRecord.id)
            .offset(offset)
            .limit(limit)
        )
        return [_cart_view(cart) for cart in session.scalars(query)]

    @app.get("/cart/{cart_id}")
    def get_cart(cart_id: int, session: DatabaseSession) -> Cart:
        return _cart_view(_get_cart(session, cart_id))

    @app.post("/cart/{cart_id}/add/{item_id}")
    def add_item_to_cart(cart_id: int, item_id: int, session: DatabaseSession) -> Cart:
        cart = _get_cart(session, cart_id, lock=True)
        _get_item(session, item_id, lock=True)
        changed = session.execute(
            update(CartItemRecord)
            .where(CartItemRecord.cart_id == cart_id, CartItemRecord.item_id == item_id)
            .values(quantity=CartItemRecord.quantity + 1)
        )
        if changed.rowcount == 0:
            session.add(CartItemRecord(cart_id=cart_id, item_id=item_id, quantity=1))
        session.flush()
        result = _cart_view(cart)
        session.commit()
        return result

    @app.post("/item", status_code=HTTPStatus.CREATED)
    def create_item(data: ItemData, response: Response, session: DatabaseSession) -> Item:
        item = ItemRecord(**data.model_dump())
        session.add(item)
        session.flush()
        session.commit()
        response.headers["Location"] = f"/item/{item.id}"
        return Item.model_validate(item)

    @app.get("/item")
    def list_items(
        session: DatabaseSession,
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(gt=0)] = 10,
        min_price: Annotated[float | None, Query(ge=0, allow_inf_nan=False)] = None,
        max_price: Annotated[float | None, Query(ge=0, allow_inf_nan=False)] = None,
        show_deleted: bool = False,
    ) -> list[Item]:
        query = select(ItemRecord)
        if not show_deleted:
            query = query.where(ItemRecord.deleted.is_(False))
        if min_price is not None:
            query = query.where(ItemRecord.price >= min_price)
        if max_price is not None:
            query = query.where(ItemRecord.price <= max_price)
        query = query.order_by(ItemRecord.id).offset(offset).limit(limit)
        return [Item.model_validate(item) for item in session.scalars(query)]

    @app.get("/item/{item_id}")
    def get_item(item_id: int, session: DatabaseSession) -> Item:
        return Item.model_validate(_get_item(session, item_id))

    @app.put("/item/{item_id}")
    def replace_item(item_id: int, data: ItemData, session: DatabaseSession) -> Item:
        item = _get_item(session, item_id, include_deleted=True, lock=True)
        for field, value in data.model_dump().items():
            setattr(item, field, value)
        session.commit()
        return Item.model_validate(item)

    @app.patch("/item/{item_id}", response_model=Item)
    def patch_item(item_id: int, data: ItemPatch, session: DatabaseSession) -> Item | Response:
        item = _get_item(session, item_id, include_deleted=True, lock=True)
        if item.deleted:
            return Response(status_code=HTTPStatus.NOT_MODIFIED)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        session.commit()
        return Item.model_validate(item)

    @app.delete("/item/{item_id}")
    def delete_item(item_id: int, session: DatabaseSession) -> Response:
        item = _get_item(session, item_id, include_deleted=True, lock=True)
        item.deleted = True
        session.commit()
        return Response(status_code=HTTPStatus.OK)

    return app


app = create_app()
