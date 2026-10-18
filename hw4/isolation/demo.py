#Демонстрация аномалий транзакций и уровней изоляции (PostgreSQL + SQLAlchemy).
from __future__ import annotations

import os
import threading
from typing import Any, Callable

from sqlalchemy import Float, Integer, String, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://shop:shop@localhost:7432/shop",
)


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "isolation_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)


engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10)


def session_with_isolation(level: str) -> Session:
    return Session(engine.execution_options(isolation_level=level))


def reset_products(*products: tuple[str, float]) -> list[int]:
    Base.metadata.drop_all(engine, tables=[Product.__table__])
    Base.metadata.create_all(engine, tables=[Product.__table__])
    ids: list[int] = []
    with Session(engine) as session:
        for name, price in products:
            row = Product(name=name, price=price)
            session.add(row)
            session.flush()
            ids.append(row.id)
        session.commit()
    return ids


def run_parallel(left: Callable[[], None], right: Callable[[], None]) -> None:
    errors: list[BaseException] = []

    def wrap(fn: Callable[[], None]) -> None:
        try:
            fn()
        except Exception as exc:
            errors.append(exc)

    threads = [
        threading.Thread(target=wrap, args=(left,)),
        threading.Thread(target=wrap, args=(right,)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
        if thread.is_alive():
            raise TimeoutError("поток не завершился за 15 секунд")
    if errors:
        raise errors[0]


def banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def print_result(label: str, observed: bool, expected: bool) -> None:
    status = "OK" if observed == expected else "UNEXPECTED"
    print(f"  {label}")
    print(f"    observed={observed} expected={expected} -> {status}")


def dirty_read(isolation_level: str) -> dict[str, Any]:
    (product_id,) = reset_products(("apple", 10.0))
    updated = threading.Event()
    reader_done = threading.Event()
    result: dict[str, Any] = {}

    def writer() -> None:
        with session_with_isolation("READ COMMITTED") as session:
            product = session.get(Product, product_id)
            assert product is not None
            product.price = 999.0
            session.flush()
            updated.set()
            if not reader_done.wait(timeout=10):
                raise TimeoutError("читатель не успел")
            session.rollback()

    def reader() -> None:
        if not updated.wait(timeout=10):
            raise TimeoutError("писатель не успел")
        with session_with_isolation(isolation_level) as session:
            product = session.get(Product, product_id)
            assert product is not None
            result["seen_price"] = product.price
            result["isolation"] = session.scalar(select(func.current_setting("transaction_isolation")))
        reader_done.set()

    run_parallel(writer, reader)
    result["dirty_read"] = result["seen_price"] == 999.0
    return result


def non_repeatable_read(isolation_level: str) -> dict[str, Any]:
    (product_id,) = reset_products(("apple", 10.0))
    first_read_done = threading.Event()
    writer_committed = threading.Event()
    result: dict[str, Any] = {}

    def reader() -> None:
        with session_with_isolation(isolation_level) as session:
            product = session.get(Product, product_id)
            assert product is not None
            result["first"] = product.price
            first_read_done.set()
            if not writer_committed.wait(timeout=10):
                raise TimeoutError("писатель не закоммитил")
            session.expire_all()
            product = session.get(Product, product_id)
            assert product is not None
            result["second"] = product.price
            result["isolation"] = session.scalar(select(func.current_setting("transaction_isolation")))

    def writer() -> None:
        if not first_read_done.wait(timeout=10):
            raise TimeoutError("читатель не прочитал")
        with session_with_isolation("READ COMMITTED") as session:
            product = session.get(Product, product_id)
            assert product is not None
            product.price = 20.0
            session.commit()
        writer_committed.set()

    run_parallel(reader, writer)
    result["non_repeatable"] = result["first"] != result["second"]
    return result


def phantom_read(isolation_level: str) -> dict[str, Any]:
    reset_products(("cheap", 10.0), ("mid", 60.0))
    first_read_done = threading.Event()
    writer_committed = threading.Event()
    result: dict[str, Any] = {}
    expensive = Product.price > 50

    def reader() -> None:
        with session_with_isolation(isolation_level) as session:
            result["first"] = session.scalar(select(func.count()).select_from(Product).where(expensive))
            first_read_done.set()
            if not writer_committed.wait(timeout=10):
                raise TimeoutError("писатель не закоммитил")
            result["second"] = session.scalar(select(func.count()).select_from(Product).where(expensive))
            result["isolation"] = session.scalar(select(func.current_setting("transaction_isolation")))

    def writer() -> None:
        if not first_read_done.wait(timeout=10):
            raise TimeoutError("читатель не прочитал")
        with session_with_isolation("READ COMMITTED") as session:
            session.add(Product(name="phantom", price=80.0))
            session.commit()
        writer_committed.set()

    run_parallel(reader, writer)
    result["phantom"] = result["first"] != result["second"]
    return result


def main() -> None:
    print("Shop isolation demos")

    # 1. Dirty read при READ UNCOMMITTED
    banner("1. Dirty read: READ UNCOMMITTED")
    ru = dirty_read("READ UNCOMMITTED")
    print(f"  isolation={ru['isolation']!r}, price={ru['seen_price']}")
    print_result("dirty read", ru["dirty_read"], expected=False)

    # 2. Нет dirty read при READ COMMITTED
    banner("2. Dirty read: READ COMMITTED")
    rc_dirty = dirty_read("READ COMMITTED")
    print(f"  isolation={rc_dirty['isolation']!r}, price={rc_dirty['seen_price']}")
    print_result("dirty read", rc_dirty["dirty_read"], expected=False)

    # 3. Non-repeatable read при READ COMMITTED
    banner("3. Non-repeatable read: READ COMMITTED")
    rc_nr = non_repeatable_read("READ COMMITTED")
    print(f"  isolation={rc_nr['isolation']!r}, price={rc_nr['first']} -> {rc_nr['second']}")
    print_result("non-repeatable read", rc_nr["non_repeatable"], expected=True)

    # 4. Нет non-repeatable read при REPEATABLE READ
    banner("4. Non-repeatable read: REPEATABLE READ")
    rr_nr = non_repeatable_read("REPEATABLE READ")
    print(f"  isolation={rr_nr['isolation']!r}, price={rr_nr['first']} -> {rr_nr['second']}")
    print_result("non-repeatable read", rr_nr["non_repeatable"], expected=False)

    # 5. Phantom read при REPEATABLE READ
    banner("5. Phantom read: REPEATABLE READ")
    rr_ph = phantom_read("REPEATABLE READ")
    print(f"  isolation={rr_ph['isolation']!r}, count={rr_ph['first']} -> {rr_ph['second']}")
    print_result("phantom read", rr_ph["phantom"], expected=False)

    # Дополнительная проверка phantom read при READ COMMITTED
    rc_ph = phantom_read("READ COMMITTED")
    print(f"  READ COMMITTED: count={rc_ph['first']} -> {rc_ph['second']}")
    print_result("phantom read", rc_ph["phantom"], expected=True)

    # 6. Нет phantom read при SERIALIZABLE
    banner("6. Phantom read: SERIALIZABLE")
    ser_ph = phantom_read("SERIALIZABLE")
    print(f"  isolation={ser_ph['isolation']!r}, count={ser_ph['first']} -> {ser_ph['second']}")
    print_result("phantom read", ser_ph["phantom"], expected=False)


if __name__ == "__main__":
    main()
