from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from .dbase import Base


class ItemDB(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    price = Column(Float)
    deleted = Column(Boolean, default=False)


class CartDB(Base):
    __tablename__ = "carts"

    id = Column(Integer, primary_key=True)


class CartItemDB(Base):
    __tablename__ = "cart_items"

    cart_id = Column(Integer, ForeignKey("carts.id"), primary_key=True)
    item_id = Column(Integer, ForeignKey("items.id"), primary_key=True)
    quantity = Column(Integer, default=1)