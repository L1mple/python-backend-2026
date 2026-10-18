from sqlalchemy import ForeignKey
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase):
    pass


class ItemRecord(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    price: Mapped[float]
    deleted: Mapped[bool] = mapped_column(default=False)


class CartItemRecord(Base):
    __tablename__ = "cart_items"

    cart_id: Mapped[int] = mapped_column(
        ForeignKey("carts.id"),
        primary_key=True,
    )
    item_id: Mapped[int] = mapped_column(
        ForeignKey("items.id"),
        primary_key=True,
    )
    quantity: Mapped[int]
    item: Mapped[ItemRecord] = relationship()


class CartRecord(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True)
    cart_items: Mapped[list[CartItemRecord]] = relationship(order_by=CartItemRecord.item_id)
