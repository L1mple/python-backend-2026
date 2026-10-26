import os
import time

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    price: Mapped[float] = mapped_column(Float)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)


class CartLine(Base):
    __tablename__ = "cart_lines"

    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id"), primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), primary_key=True)
    qty: Mapped[int] = mapped_column(Integer, default=1)


def make_engine():
    url = os.environ.get("DATABASE_URL", "sqlite://")
    if url.startswith("sqlite"):
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return create_engine(url, pool_pre_ping=True)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db():
    err = None
    for _ in range(30):
        try:
            Base.metadata.create_all(engine)
            return
        except Exception as e:
            err = e
            time.sleep(1)
    raise err


init_db()
