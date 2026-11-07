from sqlalchemy import CheckConstraint, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    price: Mapped[float] = mapped_column(CheckConstraint("price >= 0"))
    deleted: Mapped[bool] = mapped_column(default=False)


class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True)
    # В async-режиме ленивой подгрузки нет, поэтому товары корзины
    # подгружаются сразу, отдельным запросом SELECT ... WHERE cart_id IN (...)
    items: Mapped[list["CartItem"]] = relationship(
        lazy="selectin",
        order_by="CartItem.item_id",
    )


class CartItem(Base):
    __tablename__ = "cart_items"

    cart_id: Mapped[int] = mapped_column(
        ForeignKey("carts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), primary_key=True)
    quantity: Mapped[int] = mapped_column(CheckConstraint("quantity > 0"))

    item: Mapped[Item] = relationship(lazy="joined")
