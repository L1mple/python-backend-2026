from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import os
from .models import Base, Cart, CartItemOrm, CartMapper, CartOrm, Item, ItemMapper, ItemOrm


_db_url = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:password@localhost:5432/shop")
_engine = create_engine(_db_url)
_inited = False

def init_db() -> None:
    global _inited
    if not _inited:
        Base.metadata.create_all(_engine)
    _inited = True


def get_session() -> Session:
    init_db()
    return Session(_engine)


def add_item(name: str, price: float) -> Item:
    with get_session() as session:
        orm_item = ItemMapper.to_orm(Item(id=0, name=name, price=price))
        session.add(orm_item)
        session.commit()
        session.refresh(orm_item)
        return ItemMapper.to_domain(orm_item)


def get_item(item_id: int, show_deleted: bool = False) -> Item | None:
    with get_session() as session:
        query = session.query(ItemOrm).filter_by(id=item_id)
        if not show_deleted:
            query = query.filter_by(deleted=False)
        orm_item = query.first()
        return ItemMapper.to_domain(orm_item) if orm_item else None


def get_items(offset: int = 0, limit: int = 10, min_price: float | None = None, max_price: float | None = None, show_deleted: bool = False) -> list[Item]:
    with get_session() as session:
        query = session.query(ItemOrm)
        if not show_deleted:
            query = query.filter_by(deleted=False)
        if min_price is not None:
            query = query.filter(ItemOrm.price >= min_price)
        if max_price is not None:
            query = query.filter(ItemOrm.price <= max_price)
        orm_items = query.order_by(ItemOrm.id).offset(offset).limit(limit).all()
        return [ItemMapper.to_domain(orm_item) for orm_item in orm_items]


def update_item(item_id: int, name: str, price: float) -> Item | None:
    with get_session() as session:
        orm_item = session.query(ItemOrm).filter_by(id=item_id, deleted=False).first()
        if orm_item is None:
            return None
        ItemMapper.to_orm(Item(id=item_id, name=name, price=price), orm_item)
        session.commit()
        session.refresh(orm_item)
        return ItemMapper.to_domain(orm_item)


def patch_item(item_id: int, name: str | None = None, price: float | None = None) -> Item | None:
    with get_session() as session:
        orm_item = session.query(ItemOrm).filter_by(id=item_id, deleted=False).first()
        if orm_item is None:
            return None
        if name is not None:
            orm_item.name = name
        if price is not None:
            orm_item.price = price
        session.commit()
        session.refresh(orm_item)
        return ItemMapper.to_domain(orm_item)


def delete_item(item_id: int) -> None:
    with get_session() as session:
        orm_item = session.get(ItemOrm, item_id)
        if orm_item is not None:
            orm_item.deleted = True
            session.commit()


def add_cart() -> Cart:
    with get_session() as session:
        orm_cart = CartOrm()
        session.add(orm_cart)
        session.commit()
        session.refresh(orm_cart)
        return Cart(id=orm_cart.id)


def get_cart(cart_id: int) -> Cart | None:
    with get_session() as session:
        orm_cart = session.query(CartOrm).filter_by(id=cart_id).first()
        return CartMapper.to_domain(orm_cart) if orm_cart else None


def get_carts(offset: int = 0, limit: int = 10, min_price: float | None = None, max_price: float | None = None, min_quantity: int | None = None, max_quantity: int | None = None) -> list[Cart]:
    with get_session() as session:
        orm_carts = session.query(CartOrm).order_by(CartOrm.id).all()
        carts = [CartMapper.to_domain(orm_cart) for orm_cart in orm_carts]
        result = []
        for cart in carts:
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


def add_item_to_cart(cart_id: int, item_id: int) -> Cart | None:
    with get_session() as session:
        orm_cart = session.get(CartOrm, cart_id)
        orm_item = session.query(ItemOrm).filter_by(id=item_id, deleted=False).first()
        if orm_cart is None or orm_item is None:
            return None
        orm_cart_item = session.get(CartItemOrm, (cart_id, item_id))
        if orm_cart_item is None:
            session.add(CartItemOrm(cart_id=cart_id, item_id=item_id, quantity=1))
        else:
            orm_cart_item.quantity += 1
        session.commit()
        return CartMapper.to_domain(session.query(CartOrm).filter_by(id=cart_id).first())
