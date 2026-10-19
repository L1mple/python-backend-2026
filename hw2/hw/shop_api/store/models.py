from dataclasses import dataclass, field

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


# ---------- доменные модели ----------

@dataclass(slots=True)
class ItemInfo:
    name: str
    price: float


@dataclass(slots=True)
class ItemEntity:
    id: int
    info: ItemInfo
    deleted: bool = False


@dataclass(slots=True)
class PatchItemInfo:
    name: str | None = None
    price: float | None = None


@dataclass(slots=True)
class CartItemInfo:
    item_id: int
    quantity: int


@dataclass(slots=True)
class CartEntity:
    id: int
    items: list[CartItemInfo] = field(default_factory=list)


# ---------- ORM-модели ----------

class ItemORM(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    price: Mapped[float] = mapped_column(Float)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class CartORM(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True)
    items: Mapped[list["CartItemORM"]] = relationship(
        back_populates="cart", cascade="all, delete-orphan"
    )


class CartItemORM(Base):
    __tablename__ = "cart_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id"))
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=1)

    cart: Mapped["CartORM"] = relationship(back_populates="items")
    item: Mapped["ItemORM"] = relationship()
