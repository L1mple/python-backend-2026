from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Column
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class ItemOrm(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    price = Column(Float, nullable=False)
    deleted = Column(Boolean, nullable=False, default=False)

class CartOrm(Base):
    __tablename__ = "carts"
    id = Column(Integer, primary_key=True)

class CartItemOrm(Base):
    __tablename__ = "cart_items"
    cart_id = Column(
        Integer,
        ForeignKey("carts.id"),
        primary_key=True,
    )
    item_id = Column(
        Integer,
        ForeignKey("items.id"),
        primary_key=True,
    )
    quantity = Column(Integer, nullable=False, default=1)
