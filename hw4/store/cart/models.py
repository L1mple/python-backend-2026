from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from store.db import Base


@dataclass(slots=True)
class CartItemEntity:
    id: int
    name: str
    quantity: int
    available: bool


@dataclass(slots=True)
class CartEntity:
    id: int
    items: list[CartItemEntity] = field(default_factory=list)
    price: float = 0.0


class CartOrm(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True)


class CartItemOrm(Base):
    __tablename__ = "cart_items"

    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id"), primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), primary_key=True)
    quantity: Mapped[int]
