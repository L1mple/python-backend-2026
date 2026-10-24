from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shop database metadata."""


class ItemRow(Base):
    """Persistent inventory item."""

    __tablename__ = "items"
    __table_args__ = (
        CheckConstraint("price >= 0 AND price <= 1.7976931348623157e308"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    price: Mapped[float] = mapped_column(Float)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class CartRow(Base):
    """Persistent cart identifier."""

    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True)


class CartPosition(Base):
    """Unique item quantity in a cart."""

    __tablename__ = "cart_positions"
    __table_args__ = (
        UniqueConstraint("cart_id", "item_id"),
        CheckConstraint("quantity > 0"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id"))
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    quantity: Mapped[int]
