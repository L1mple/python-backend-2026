import os

from sqlalchemy import ForeignKey, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship
from sqlalchemy.pool import StaticPool

# docker'da postgres veriliyor, testlerde degisken yok -> bellekte sqlite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite://")

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_engine(DATABASE_URL)


class Base(DeclarativeBase):
    pass


class ItemOrm(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    price: Mapped[float]
    deleted: Mapped[bool] = mapped_column(default=False)


class CartOrm(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True)
    items: Mapped[list["CartItemOrm"]] = relationship(order_by="CartItemOrm.item_id")


class CartItemOrm(Base):
    __tablename__ = "cart_items"

    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id"), primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), primary_key=True)
    quantity: Mapped[int] = mapped_column(default=1)
    item: Mapped[ItemOrm] = relationship()


Base.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
