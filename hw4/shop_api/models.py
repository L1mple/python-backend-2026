"""Таблицы БД."""

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from shop_api.database import Base


class ItemORM(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    # Float(53) = double precision (в MySQL обычный FLOAT - это 4 байта, нам этого мало)
    price: Mapped[float] = mapped_column(Float(53))
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")


class CartORM(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)


class CartItemORM(Base):
    """Товар в корзине: пара (корзина, товар) и количество."""

    __tablename__ = "cart_items"

    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id"), primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
