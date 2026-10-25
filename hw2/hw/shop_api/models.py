from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Float, Boolean, Table, Column, Integer, ForeignKey
from decimal import Decimal

from shop_api.database import Base


class Item(Base):
    __tablename__ = "items"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[Decimal] = mapped_column(Float, nullable=False)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    cart_items: Mapped[list["CartItem"]] = relationship(back_populates="item")


class Cart(Base):
    __tablename__ = "carts"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cart_items: Mapped[list["CartItem"]] = relationship(back_populates="cart", cascade="all, delete-orphan")


class CartItem(Base):
    __tablename__ = "cart_items"
    
    cart_id: Mapped[int] = mapped_column(Integer, ForeignKey("carts.id", ondelete="CASCADE"), primary_key=True)
    item_id: Mapped[int] = mapped_column(Integer, ForeignKey("items.id", ondelete="CASCADE"), primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    
    item: Mapped["Item"] = relationship(back_populates="cart_items")
    cart: Mapped["Cart"] = relationship(back_populates="cart_items")
