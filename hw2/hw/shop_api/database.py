import os
from collections.abc import Iterator

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    pass


class ItemRow(Base):
    __tablename__ = "items"
    __table_args__ = (CheckConstraint("price >= 0"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class CartRow(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True)


class CartItemRow(Base):
    __tablename__ = "cart_items"
    __table_args__ = (CheckConstraint("quantity > 0"),)

    cart_id: Mapped[int] = mapped_column(
        ForeignKey("carts.id", ondelete="CASCADE"), primary_key=True
    )
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)


engine = create_engine(
    os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://shop:shop@localhost:7432/shop"
    ),
    pool_pre_ping=True,
)


def initialize() -> None:
    Base.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session, session.begin():
        yield session
