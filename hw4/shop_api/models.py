from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shop_api.database import Base


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (CheckConstraint("price >= 0", name="item_price_non_negative"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True)
    items: Mapped[list["CartItem"]] = relationship(
        back_populates="cart",
        cascade="all, delete-orphan",
    )


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="cart_item_quantity_positive"),
    )

    cart_id: Mapped[int] = mapped_column(
        ForeignKey("carts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    item_id: Mapped[int] = mapped_column(
        ForeignKey("items.id"),
        primary_key=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    cart: Mapped[Cart] = relationship(back_populates="items")
    item: Mapped[Item] = relationship()
