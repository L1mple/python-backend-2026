import os
from functools import lru_cache

from sqlalchemy import Boolean, CheckConstraint, Float, ForeignKey, Integer, Text, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.engine import make_url


class Base(DeclarativeBase):
    pass


class ItemRow(Base):
    __tablename__ = "items"
    __table_args__ = (CheckConstraint("price >= 0"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    price: Mapped[float] = mapped_column(Float(53))
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class CartRow(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True)


class CartItemRow(Base):
    __tablename__ = "cart_items"
    __table_args__ = (CheckConstraint("quantity > 0"),)

    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id"), primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer)


def make_engine(url: str):
    url = make_url(url)
    options = {"pool_pre_ping": True}
    if url.get_backend_name() == "sqlite":
        options["connect_args"] = {"check_same_thread": False, "timeout": 30}
    else:
        options["isolation_level"] = "REPEATABLE READ"
    engine = create_engine(url, **options)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
    return engine


@lru_cache
def get_engine():
    engine = make_engine(os.getenv("DATABASE_URL", "sqlite:///./shop.db"))
    # Lazy initialization also supports TestClient used without a lifespan context.
    Base.metadata.create_all(engine)
    return engine


def get_session():
    with Session(get_engine()) as session:
        yield session
