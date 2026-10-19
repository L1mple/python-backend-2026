from dataclasses import dataclass, field
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship


@dataclass(slots=True)
class Item:
    id: int
    name: str
    price: float
    deleted: bool = False


@dataclass(slots=True)
class CartItem:
    id: int
    name: str
    quantity: int
    available: bool


@dataclass(slots=True)
class Cart:
    id: int
    items: list[CartItem] = field(default_factory=list)
    price: float = 0.


Base = declarative_base()


class ItemOrm(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    deleted = Column(Boolean, nullable=False, default=False)


class CartOrm(Base):
    __tablename__ = "carts"

    id = Column(Integer, primary_key=True)
    items = relationship("CartItemOrm", order_by="CartItemOrm.item_id", cascade="all, delete-orphan")


class CartItemOrm(Base):
    __tablename__ = "cart_items"

    cart_id = Column(Integer, ForeignKey("carts.id"), primary_key=True)
    item_id = Column(Integer, ForeignKey("items.id"), primary_key=True)
    quantity = Column(Integer, nullable=False)
    item = relationship("ItemOrm")


class ItemMapper:
    @staticmethod
    def to_domain(orm_item: ItemOrm) -> Item:
        return Item(id=orm_item.id, name=orm_item.name, price=orm_item.price, deleted=orm_item.deleted)

    @staticmethod
    def to_orm(item: Item, orm_item: ItemOrm | None = None) -> ItemOrm:
        if orm_item is None:
            orm_item = ItemOrm()
        orm_item.name = item.name
        orm_item.price = item.price
        orm_item.deleted = item.deleted
        return orm_item


class CartItemMapper:
    @staticmethod
    def to_domain(orm_cart_item: CartItemOrm) -> CartItem:
        return CartItem(id=orm_cart_item.item_id, name=orm_cart_item.item.name, quantity=orm_cart_item.quantity, available=not orm_cart_item.item.deleted)

    @staticmethod
    def to_orm(cart_id: int, cart_item: CartItem) -> CartItemOrm:
        return CartItemOrm(cart_id=cart_id, item_id=cart_item.id, quantity=cart_item.quantity)


class CartMapper:
    @staticmethod
    def to_domain(orm_cart: CartOrm) -> Cart:
        items = [CartItemMapper.to_domain(orm_item) for orm_item in orm_cart.items]
        price = sum(orm_item.item.price * orm_item.quantity for orm_item in orm_cart.items if not orm_item.item.deleted)
        return Cart(id=orm_cart.id, items=items, price=price)

    @staticmethod
    def to_orm(cart: Cart) -> CartOrm:
        orm_cart = CartOrm()
        orm_cart.items = [CartItemMapper.to_orm(cart.id, item) for item in cart.items]
        return orm_cart
