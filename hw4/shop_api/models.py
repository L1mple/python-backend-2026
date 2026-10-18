from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from shop_api.db import Base


class ItemOrm(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    price: Mapped[float]
    deleted: Mapped[bool] = mapped_column(default=False)


class CartOrm(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True)


class CartItemOrm(Base):
    __tablename__ = "cart_items"

    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id"), primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), primary_key=True)
    quantity: Mapped[int] = mapped_column(default=1)

