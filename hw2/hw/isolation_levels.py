# Две транзакции (T1 и T2) — это две сессии с заданным уровнем изоляции

import os
from sqlalchemy import Column, Double, Integer, create_engine, func, select, text, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, declarative_base


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://shop:shop@localhost:3306/shop",
)

engine = create_engine(DATABASE_URL)
Base = declarative_base()


class DemoItem(Base):

    __tablename__ = "isolation_demo_items"

    id = Column(Integer, primary_key=True)
    price = Column(Double, nullable=False)


def transaction(level: str) -> Session:
    return Session(engine.execution_options(isolation_level=level))


def prepare(*prices: float) -> None:
    with Session(engine) as session, session.begin():
        session.query(DemoItem).delete()
        session.add_all(DemoItem(id=i, price=p) for i, p in enumerate(prices, start=1))


def price_of(session: Session) -> float:
    return session.scalar(select(DemoItem.price).where(DemoItem.id == 1))


def dirty_read(level: str) -> tuple[str, bool]:
    # T2 читает цену, которую T1 изменила, но не закоммитила
    prepare(100)
    with transaction(level) as t1, transaction(level) as t2:
        t1.execute(update(DemoItem).where(DemoItem.id == 1).values(price=999))
        seen = price_of(t2)
        t1.rollback()
    return f"T1 ставит 999 без COMMIT, T2 видит {seen:g}", seen == 999


def non_repeatable_read(level: str) -> tuple[str, bool]:
    # T1 дважды читает строку, а между чтениями T2 меняет её и коммитит
    prepare(100)
    with transaction(level) as t1, transaction(level) as t2:
        first = price_of(t1)
        t2.execute(update(DemoItem).where(DemoItem.id == 1).values(price=200))
        t2.commit()
        second = price_of(t1)
        t1.commit()
    return f"T1 читает {first:g}, затем {second:g}", first != second


def phantom_read(level: str) -> tuple[str, bool]:
    # T1 дважды считает строки, а между подсчётами T2 добавляет новую.
    count = select(func.count()).select_from(DemoItem)
    prepare(100, 100)
    with transaction(level) as t1, transaction(level) as t2:
        first = t1.scalar(count)
        t2.execute(text("SET innodb_lock_wait_timeout = 1"))
        try:
            t2.add(DemoItem(id=3, price=100))
            t2.commit()
            t2_status = "T2 добавила строку"
        except OperationalError:
            t2.rollback()
            t2_status = "T2 заблокирована"
        second = t1.scalar(count.with_for_update())
        t1.commit()
    return f"{t2_status}, T1 считает строки: {first}, затем {second}", first != second


def main() -> None:
    scenarios = [
        ("dirty read", dirty_read, "READ UNCOMMITTED"),
        ("dirty read", dirty_read, "READ COMMITTED"),
        ("non-repeatable read", non_repeatable_read, "READ COMMITTED"),
        ("non-repeatable read", non_repeatable_read, "REPEATABLE READ"),
        ("phantom read", phantom_read, "REPEATABLE READ"),
        ("phantom read", phantom_read, "SERIALIZABLE"),
    ]

    Base.metadata.create_all(engine)
    try:
        print(f"{'Аномалия':<21}{'Уровень':<18}{'Результат':<11}Что произошло")
        for anomaly, demo, level in scenarios:
            details, happened = demo(level)
            print(f"{anomaly:<21}{level:<18}{'ЕСТЬ' if happened else 'нет':<11}{details}")
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


if __name__ == "__main__":
    main()
