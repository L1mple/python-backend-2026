from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class ItemRow(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    price: Mapped[float]
    deleted: Mapped[bool] = mapped_column(default=False)


class CartRow(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True)
    price: Mapped[float] = mapped_column(default=0.0)

    items: Mapped[list[CartItemRow]] = relationship(
        back_populates="cart",
        cascade="all, delete-orphan",
    )


class CartItemRow(Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("cart_id", "item_id", name="uq_cart_items_cart_item"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id", ondelete="CASCADE"))
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    name: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[int]
    available: Mapped[bool]

    cart: Mapped[CartRow] = relationship(back_populates="items")
