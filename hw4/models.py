from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)


class CartItem(Base):
    __tablename__ = "cart_items"

    cart_id: Mapped[int] = mapped_column(
        ForeignKey("carts.id"), primary_key=True
    )
    item_id: Mapped[int] = mapped_column(
        ForeignKey("items.id"), primary_key=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
