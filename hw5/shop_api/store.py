from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from shop_api.db import SessionLocal
from shop_api.models import CartItemOrm, CartOrm, ItemOrm


# Доменные записи без привязки к БД

@dataclass(slots=True)
class ItemRecord:
    id: int
    name: str
    price: float
    deleted: bool = False


@dataclass(slots=True)
class CartRecord:
    id: int
    items: dict[int, int] = field(default_factory=dict)


# Маппер: строка таблицы - доменная запись 

def _to_item_record(item: ItemOrm) -> ItemRecord:
    return ItemRecord(
        id=item.id, name=item.name, price=item.price, deleted=item.deleted
    )


# Товары

def add_item(name: str, price: float) -> ItemRecord:
    with SessionLocal.begin() as session:
        item = ItemOrm(name=name, price=price)
        session.add(item)
        session.flush()
        return _to_item_record(item)


def get_item(item_id: int) -> ItemRecord | None:
    """Товар по id, включая удалённые (решение показывать или нет через роутер)"""
    with SessionLocal.begin() as session:
        item = session.get(ItemOrm, item_id)
        return _to_item_record(item) if item else None


def list_items(
    offset: int = 0,
    limit: int = 10,
    min_price: float | None = None,
    max_price: float | None = None,
    show_deleted: bool = False,
) -> list[ItemRecord]:
    query = select(ItemOrm).order_by(ItemOrm.id)
    if not show_deleted:
        query = query.where(ItemOrm.deleted.is_(False))
    if min_price is not None:
        query = query.where(ItemOrm.price >= min_price)
    if max_price is not None:
        query = query.where(ItemOrm.price <= max_price)
    query = query.offset(offset).limit(limit)

    with SessionLocal.begin() as session:
        return [_to_item_record(item) for item in session.scalars(query)]


def update_item(item_id: int, **fields) -> ItemRecord | None:
    """Обновить живой товар; None когда товара нет или он удалён."""
    with SessionLocal.begin() as session:
        item = session.get(ItemOrm, item_id)
        if item is None or item.deleted:
            return None
        for name, value in fields.items():
            setattr(item, name, value)
        return _to_item_record(item)



def delete_item(item_id: int) -> bool:
    """Мягкое удаление: строка остаётся, ставим флаг deleted"""
    with SessionLocal.begin() as session:
        item = session.get(ItemOrm, item_id)
        if item is None:
            return False
        item.deleted = True
        return True


# Корзины 

def add_cart() -> CartRecord:
    with SessionLocal.begin() as session:
        cart = CartOrm()
        session.add(cart)
        session.flush()
        return CartRecord(id=cart.id)


def get_cart(cart_id: int) -> CartRecord | None:
    with SessionLocal.begin() as session:
        if session.get(CartOrm, cart_id) is None:
            return None
        rows = session.scalars(
            select(CartItemOrm).where(CartItemOrm.cart_id == cart_id)
        )
        return CartRecord(id=cart_id, items={row.item_id: row.quantity for row in rows})


def list_carts() -> list[CartRecord]:
    with SessionLocal.begin() as session:
        cart_ids = session.scalars(select(CartOrm.id).order_by(CartOrm.id))
        carts = {cart_id: CartRecord(id=cart_id) for cart_id in cart_ids}
        for row in session.scalars(select(CartItemOrm)):
            carts[row.cart_id].items[row.item_id] = row.quantity
        return list(carts.values())


def add_item_to_cart(cart_id: int, item_id: int) -> None:
    """Положить товар в корзину: новая строка с quantity=1 или +1 к существующей делаем одним запросом"""
    statement = (
        insert(CartItemOrm)
        .values(cart_id=cart_id, item_id=item_id, quantity=1)
        .on_conflict_do_update(
            index_elements=[CartItemOrm.cart_id, CartItemOrm.item_id],
            set_={"quantity": CartItemOrm.quantity + 1},
        )
    )
    with SessionLocal.begin() as session:
        session.execute(statement)
