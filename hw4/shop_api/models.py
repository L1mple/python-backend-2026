from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Identity, Numeric, Text, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (CheckConstraint("price >= 0", name="items_price_nonnegative"),)

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    price: Mapped[Decimal] = mapped_column(Numeric)
    deleted: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    entries: Mapped[list["CartItem"]] = relationship(order_by="CartItem.item_id")


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="cart_items_quantity_positive"),
    )

    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id"), primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), primary_key=True)
    quantity: Mapped[int]
    item: Mapped[Item] = relationship()
