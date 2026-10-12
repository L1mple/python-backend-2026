"""SQLAlchemy tables and one transaction per HTTP request."""

import os
from collections.abc import Iterator

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://shop:shop@127.0.0.1:7432/shop")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)


class Base(DeclarativeBase):
    pass


class ItemRecord(Base):
    __tablename__ = "items"
    __table_args__ = (CheckConstraint("price >= 0"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    price: Mapped[float]
    deleted: Mapped[bool] = mapped_column(default=False)


class CartRecord(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True)


class CartLineRecord(Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("cart_id", "item_id"),
        CheckConstraint("quantity > 0"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    quantity: Mapped[int]


def get_session() -> Iterator[Session]:
    # The context commits on success and rolls back on exceptions.
    with Session(engine) as session, session.begin():
        yield session
