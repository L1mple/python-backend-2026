import os

from sqlalchemy import Boolean, CheckConstraint, Float, ForeignKey, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ItemRow(Base):
    __tablename__ = "items"
    __table_args__ = (CheckConstraint("price >= 0"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    price: Mapped[float] = mapped_column(Float)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class CartRow(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True)
    lines: Mapped[list["CartLine"]] = relationship(order_by="CartLine.item_id")


class CartLine(Base):
    __tablename__ = "cart_items"
    __table_args__ = (CheckConstraint("quantity > 0"),)

    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id"), primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), primary_key=True)
    quantity: Mapped[int] = mapped_column(default=1)
    item: Mapped[ItemRow] = relationship()


database_url = os.getenv("DATABASE_URL", "sqlite:///./shop.db")
engine = create_engine(
    database_url,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
)
Base.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        with session.begin():
            yield session
