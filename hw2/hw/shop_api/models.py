from dataclasses import dataclass

from sqlalchemy import Boolean, CheckConstraint, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from shop_api.database import Base


class ItemEntity(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )


class CartEntity(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True)


class CartItemEntity(Base):
    __tablename__ = "cart_items"
    __table_args__ = (CheckConstraint("quantity > 0"),)

    cart_id: Mapped[int] = mapped_column(
        ForeignKey("carts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    item_id: Mapped[int] = mapped_column(
        ForeignKey("items.id"),
        primary_key=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


@dataclass(frozen=True, slots=True)
class CartLine:
    id: int
    name: str
    quantity: int
    available: bool


@dataclass(frozen=True, slots=True)
class CartView:
    id: int
    items: list[CartLine]
    price: float
