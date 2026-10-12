from sqlalchemy import CheckConstraint, Float, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ItemRow(Base):
    __tablename__ = "items"
    __table_args__ = (CheckConstraint("price >= 0"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    price: Mapped[float] = mapped_column(Float(53))
    deleted: Mapped[bool] = mapped_column(default=False)


class CartRow(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True)


class CartLine(Base):
    __tablename__ = "cart_lines"
    __table_args__ = (CheckConstraint("quantity > 0"),)

    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id"), primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), primary_key=True)
    quantity: Mapped[int]
