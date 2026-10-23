import os
from collections.abc import Iterator

from sqlalchemy import CheckConstraint, ForeignKey, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///shop.db")

engine = create_engine(
    DATABASE_URL,
    connect_args=(
        {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
    ),
)


class Base(DeclarativeBase):
    pass


class ItemOrm(Base):
    __tablename__ = "items"
    __table_args__ = (CheckConstraint("price >= 0", name="item_price_non_negative"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    price: Mapped[float]
    deleted: Mapped[bool] = mapped_column(default=False)


class CartOrm(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True)
    items: Mapped[list["CartItemOrm"]] = relationship(lazy="selectin")


class CartItemOrm(Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="cart_item_quantity_positive"),
    )

    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id"), primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), primary_key=True)
    quantity: Mapped[int]

    item: Mapped[ItemOrm] = relationship(lazy="joined")


Base.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
