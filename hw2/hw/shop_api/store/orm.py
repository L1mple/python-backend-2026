from sqlalchemy import Boolean, Column, Double, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


class ItemOrm(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    price = Column(Double, nullable=False)
    deleted = Column(Boolean, nullable=False, default=False)


class CartOrm(Base):
    __tablename__ = "carts"

    id = Column(Integer, primary_key=True)
    items = relationship("CartItemOrm", order_by="CartItemOrm.item_id", lazy="selectin")


class CartItemOrm(Base):
    __tablename__ = "cart_items"

    cart_id = Column(Integer, ForeignKey("carts.id"), primary_key=True)
    item_id = Column(Integer, ForeignKey("items.id"), primary_key=True)
    quantity = Column(Integer, nullable=False, default=0)
    item = relationship("ItemOrm", lazy="joined")
