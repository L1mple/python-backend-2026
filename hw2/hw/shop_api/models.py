from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from shop_api.database import Base


class ItemModel(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    deleted = Column(Boolean, nullable=False, default=False)

    cart_links = relationship("CartItemModel", back_populates="item")


class CartModel(Base):
    __tablename__ = "carts"

    id = Column(Integer, primary_key=True, autoincrement=True)

    items = relationship(
        "CartItemModel",
        back_populates="cart",
        cascade="all, delete-orphan",
    )


class CartItemModel(Base):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("cart_id", "item_id", name="uq_cart_item"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    cart_id = Column(Integer, ForeignKey("carts.id", ondelete="CASCADE"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)

    cart = relationship("CartModel", back_populates="items")
    item = relationship("ItemModel", back_populates="cart_links")
