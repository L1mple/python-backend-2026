import os
from pathlib import Path

from sqlalchemy import Boolean, CheckConstraint, Float, ForeignKey, Text, create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


class ItemRecord(Base):
    __tablename__ = "items"
    __table_args__ = (CheckConstraint("price >= 0", name="nonnegative_price"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    price: Mapped[float] = mapped_column(Float(53))
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class CartRecord(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True)
    items: Mapped[list["CartItemRecord"]] = relationship(order_by="CartItemRecord.item_id")


class CartItemRecord(Base):
    __tablename__ = "cart_items"
    __table_args__ = (CheckConstraint("quantity > 0", name="positive_quantity"),)

    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id"), primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), primary_key=True)
    quantity: Mapped[int] = mapped_column(default=1)
    item: Mapped[ItemRecord] = relationship(lazy="joined")


def create_database(database_url: str | None = None) -> Engine:
    default_path = Path(__file__).with_name("shop.sqlite3")
    url = make_url(database_url or os.getenv("DATABASE_URL") or f"sqlite:///{default_path}")
    options = {}
    if url.get_backend_name() == "sqlite":
        options["connect_args"] = {"check_same_thread": False, "timeout": 30}
        if url.database in (None, "", ":memory:"):
            options["poolclass"] = StaticPool

    engine = create_engine(url, pool_pre_ping=True, **options)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def configure_sqlite(dbapi_connection, _):
            dbapi_connection.isolation_level = None
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

        @event.listens_for(engine, "begin")
        def begin_sqlite(connection):
            write = connection.get_execution_options().get("write_transaction", False)
            connection.exec_driver_sql("BEGIN IMMEDIATE" if write else "BEGIN")

    Base.metadata.create_all(engine)
    return engine
