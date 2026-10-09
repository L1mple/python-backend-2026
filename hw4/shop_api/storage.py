from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, joinedload

from shop_api import monitoring
from shop_api.models import Cart, CartItem, Item
from shop_api.schemas import CartItemResponse, CartResponse


class NotFoundError(Exception):
    pass


class ItemDeletedError(Exception):
    pass


def create_item(session: Session, *, name: str, price: float) -> Item:
    with session.begin():
        item = Item(name=name, price=Decimal(str(price)))
        session.add(item)
        session.flush()
    monitoring.items_created.inc()
    return item


def get_item(
    session: Session,
    item_id: int,
    *,
    include_deleted: bool = False,
    lock: bool = False,
) -> Item:
    query = select(Item).where(Item.id == item_id)
    if not include_deleted:
        query = query.where(Item.deleted.is_(False))
    if lock:
        query = query.with_for_update()
    item = session.scalar(query)
    if item is None:
        raise NotFoundError(f"Item {item_id} not found")
    return item


def list_items(
    session: Session,
    *,
    offset: int = 0,
    limit: int = 10,
    min_price: float | None = None,
    max_price: float | None = None,
    show_deleted: bool = False,
) -> list[Item]:
    query = select(Item)
    if not show_deleted:
        query = query.where(Item.deleted.is_(False))
    if min_price is not None:
        query = query.where(Item.price >= Decimal(str(min_price)))
    if max_price is not None:
        query = query.where(Item.price <= Decimal(str(max_price)))
    return list(session.scalars(query.order_by(Item.id).offset(offset).limit(limit)))


def replace_item(session: Session, item_id: int, *, name: str, price: float) -> Item:
    with session.begin():
        item = get_item(session, item_id, lock=True)
        item.name = name
        item.price = Decimal(str(price))
    return item


def patch_item(
    session: Session, item_id: int, *, changes: dict[str, str | float]
) -> Item:
    with session.begin():
        item = get_item(session, item_id, include_deleted=True, lock=True)
        if item.deleted:
            raise ItemDeletedError(f"Item {item_id} is deleted")
        if "name" in changes:
            item.name = str(changes["name"])
        if "price" in changes:
            item.price = Decimal(str(changes["price"]))
    return item


def delete_item(session: Session, item_id: int) -> None:
    with session.begin():
        item = get_item(session, item_id, include_deleted=True, lock=True)
        item.deleted = True


def create_cart(session: Session) -> Cart:
    with session.begin():
        cart = Cart()
        session.add(cart)
        session.flush()
    monitoring.carts_created.inc()
    return cart


def get_cart(session: Session, cart_id: int) -> Cart:
    query = (
        select(Cart)
        .where(Cart.id == cart_id)
        .options(joinedload(Cart.entries).joinedload(CartItem.item))
    )
    cart = session.execute(query).unique().scalar_one_or_none()
    if cart is None:
        raise NotFoundError(f"Cart {cart_id} not found")
    return cart


def add_item_to_cart(session: Session, cart_id: int, item_id: int) -> None:
    with session.begin():
        if session.get(Cart, cart_id) is None:
            raise NotFoundError(f"Cart {cart_id} not found")
        # Shared lock permits parallel additions, but excludes a concurrent
        # soft delete until the addition has committed.
        item = session.scalar(
            select(Item)
            .where(Item.id == item_id, Item.deleted.is_(False))
            .with_for_update(read=True)
        )
        if item is None:
            raise NotFoundError(f"Item {item_id} not found")
        query = insert(CartItem).values(cart_id=cart_id, item_id=item_id, quantity=1)
        session.execute(query.on_conflict_do_update(
            index_elements=[CartItem.cart_id, CartItem.item_id],
            set_={"quantity": CartItem.quantity + 1},
        ))
    monitoring.cart_additions.inc()


def build_cart_response(cart: Cart) -> CartResponse:
    price = Decimal("0")
    items_response = []
    for entry in cart.entries:
        item = entry.item
        available = not item.deleted
        if available:
            price += item.price * entry.quantity
        items_response.append(CartItemResponse(
            id=item.id, name=item.name, quantity=entry.quantity, available=available,
        ))
    return CartResponse(id=cart.id, items=items_response, price=float(price))


def list_carts(
    session: Session,
    *,
    offset: int = 0,
    limit: int = 10,
    min_price: float | None = None,
    max_price: float | None = None,
    min_quantity: int | None = None,
    max_quantity: int | None = None,
) -> list[CartResponse]:
    totals = (
        select(
            Cart.id.label("cart_id"),
            func.coalesce(func.sum(case(
                (Item.deleted.is_(False), Item.price * CartItem.quantity),
                else_=0,
            )), 0).label("price"),
            func.coalesce(func.sum(CartItem.quantity), 0).label("quantity"),
        )
        .outerjoin(CartItem, CartItem.cart_id == Cart.id)
        .outerjoin(Item, Item.id == CartItem.item_id)
        .group_by(Cart.id)
        .subquery()
    )
    query = select(Cart).join(totals, totals.c.cart_id == Cart.id)
    if min_price is not None:
        query = query.where(totals.c.price >= Decimal(str(min_price)))
    if max_price is not None:
        query = query.where(totals.c.price <= Decimal(str(max_price)))
    if min_quantity is not None:
        query = query.where(totals.c.quantity >= min_quantity)
    if max_quantity is not None:
        query = query.where(totals.c.quantity <= max_quantity)
    query = (
        query.order_by(Cart.id).offset(offset).limit(limit)
        .options(joinedload(Cart.entries).joinedload(CartItem.item))
    )
    # Filtering, pagination and loading entries run in one SQL statement.
    carts = session.execute(query).unique().scalars().all()
    return [build_cart_response(cart) for cart in carts]
