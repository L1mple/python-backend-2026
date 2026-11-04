"""Демонстрация аномалий транзакций и уровней изоляции (SQLAlchemy).

Для каждой аномалии открываем две параллельные транзакции (T1 и T2) и смотрим,
что видит T1 при разных уровнях изоляции:

  * dirty read          - T1 видит чужое НЕЗАФИКСИРОВАННОЕ изменение;
  * non-repeatable read - T1 читает одну и ту же строку дважды и получает разные значения;
  * phantom read        - T1 дважды выполняет один и тот же запрос по условию и получает
                          разный набор строк (между запросами T2 добавил подходящую строку).

Запуск (из папки hw4, нужны поднятые БД, см. README):

    python -m isolation.demo --db postgres
    python -m isolation.demo --db mysql

Результат каждого сценария сравнивается с ожидаемым для этой БД; если что-то
не совпало, скрипт завершается с ненулевым кодом.
"""

import argparse
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import (
    Column,
    Connection,
    Engine,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    delete,
    func,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.exc import DBAPIError

DEFAULT_URLS = {
    "postgres": "postgresql+psycopg://shop:shop@localhost:5432/shop",
    "mysql": "mysql+pymysql://shop:shop@localhost:3307/shop",
}

# Учебная таблица: товары с ценой. Цены целые, чтобы вывод был простым.
metadata = MetaData()
demo_items = Table(
    "demo_items",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(50), nullable=False),
    Column("price", Integer, nullable=False),
)

READ_UNCOMMITTED = "READ UNCOMMITTED"
READ_COMMITTED = "READ COMMITTED"
REPEATABLE_READ = "REPEATABLE READ"
SERIALIZABLE = "SERIALIZABLE"


@dataclass
class Outcome:
    anomaly: bool  # воспроизвелась ли аномалия
    details: str  # что именно мы увидели


@dataclass
class Scenario:
    title: str
    anomaly_name: str
    level: str
    run: Callable[[Engine], Outcome] | dict[str, Callable[[Engine], Outcome]]  # одна функция или своя на каждую БД
    # Ожидаемый результат (воспроизводится ли аномалия) для каждой БД
    expected: dict[str, bool]
    # Пояснение для случаев, когда БД ведет себя иначе, чем описано в учебниках
    note: dict[str, str]


def reset_table(engine: Engine) -> None:
    """Пересоздает таблицу и кладет в нее три товара: Milk(50), Bread(150), Cheese(200)."""
    metadata.drop_all(engine, tables=[demo_items])
    metadata.create_all(engine, tables=[demo_items])
    with engine.begin() as conn:
        conn.execute(
            insert(demo_items),
            [{"name": "Milk", "price": 50}, {"name": "Bread", "price": 150}, {"name": "Cheese", "price": 200}],
        )


def open_tx(engine: Engine, level: str) -> Connection:
    """Новое соединение с заданным уровнем изоляции. Транзакция начнется при первом запросе."""
    return engine.connect().execution_options(isolation_level=level)


def milk_price(conn: Connection) -> int:
    return conn.execute(select(demo_items.c.price).where(demo_items.c.name == "Milk")).scalar_one()


def expensive_count(conn: Connection) -> int:
    """Сколько товаров дороже 100 (изначально 2: Bread и Cheese)."""
    return conn.execute(select(func.count()).select_from(demo_items).where(demo_items.c.price > 100)).scalar_one()


# ---------------------------------------------------------------------------
# Сценарии
# ---------------------------------------------------------------------------


def dirty_read(level: str):
    """T1 меняет цену молока и НЕ фиксирует. T2 читает цену на заданном уровне."""

    def run(engine: Engine) -> Outcome:
        t1, t2 = open_tx(engine, READ_COMMITTED), open_tx(engine, level)
        try:
            t1.execute(update(demo_items).where(demo_items.c.name == "Milk").values(price=999))
            seen = milk_price(t2)
        finally:
            t1.rollback()  # T1 передумала: изменение откатывается
            t2.rollback()
            t1.close()
            t2.close()
        return Outcome(
            anomaly=seen == 999,
            details=f"T1 поставила цену 999 и не зафиксировала; T2 прочитала цену = {seen} (в БД лежало 50)",
        )

    return run


def non_repeatable_read(level: str):
    """T1 дважды читает цену молока, между чтениями T2 меняет ее и фиксирует."""

    def run(engine: Engine) -> Outcome:
        t1 = open_tx(engine, level)
        try:
            first = milk_price(t1)
            with engine.begin() as t2:
                t2.execute(update(demo_items).where(demo_items.c.name == "Milk").values(price=70))
            second = milk_price(t1)
        finally:
            t1.rollback()
            t1.close()
        return Outcome(
            anomaly=first != second,
            details=f"T1 прочитала цену {first}, T2 изменила ее на 70 и зафиксировала; T1 читает снова: {second}",
        )

    return run


def phantom_read_repeatable_read(engine: Engine) -> Outcome:
    """T1 считает дорогие товары, T2 добавляет еще один дорогой и фиксирует, T1 считает снова.

    Обычный повторный SELECT на REPEATABLE READ в обеих БД показывает прежний снимок.
    Но в MySQL/InnoDB призрак все равно "просачивается": стоит T1 сделать UPDATE по тому же
    условию, как T1 начинает видеть строку T2 (UPDATE работает с последними зафиксированными
    данными, а измененная им строка становится видимой для T1; важно, чтобы значение реально
    поменялось). В PostgreSQL UPDATE тоже работает по снимку, поэтому там призрака нет.
    """

    t1 = open_tx(engine, REPEATABLE_READ)
    try:
        before = expensive_count(t1)
        with engine.begin() as t2:
            t2.execute(insert(demo_items).values(name="Wine", price=500))
        plain = expensive_count(t1)
        t1.execute(update(demo_items).where(demo_items.c.price > 100).values(name="checked"))
        after_update = expensive_count(t1)
    finally:
        t1.rollback()
        t1.close()
    return Outcome(
        anomaly=after_update != before,
        details=(
            f"T1 насчитала дорогих товаров: {before}; T2 добавила Wine(500) и зафиксировала; "
            f"повторный SELECT: {plain}; после UPDATE по тому же условию: {after_update}"
        ),
    )


def phantom_read_serializable_mysql(engine: Engine) -> Outcome:
    """MySQL, SERIALIZABLE: SELECT берет разделяемые блокировки на диапазон, вставка T2 блокируется."""
    t1 = open_tx(engine, SERIALIZABLE)
    blocked = False
    try:
        before = expensive_count(t1)

        def try_insert() -> None:
            nonlocal blocked
            with engine.connect() as t2:
                t2.execute(text("SET SESSION innodb_lock_wait_timeout = 2"))
                try:
                    t2.execute(insert(demo_items).values(name="Wine", price=500))
                    t2.commit()
                except DBAPIError:
                    blocked = True  # не дождались блокировки: T1 держит диапазон
                    t2.rollback()

        thread = threading.Thread(target=try_insert)
        thread.start()
        thread.join()
        after = expensive_count(t1)
    finally:
        t1.rollback()
        t1.close()
    return Outcome(
        anomaly=after != before,
        details=(
            f"T1 насчитала {before}; вставка T2 {'заблокирована (Lock wait timeout)' if blocked else 'прошла'}; "
            f"T1 считает снова: {after}"
        ),
    )


def phantom_read_serializable_postgres(engine: Engine) -> Outcome:
    """PostgreSQL, SERIALIZABLE: повторное чтение стабильно, а конфликтующая запись отклоняется.

    Классический пример: T1 и T2 считают дорогие товары и каждая добавляет еще один "на основании
    увиденного". Если бы транзакции шли строго по очереди, вторая увидела бы товар первой. Параллельно
    это невозможно, поэтому PostgreSQL откатывает одну из них (ошибка сериализации).
    """
    t1, t2 = open_tx(engine, SERIALIZABLE), open_tx(engine, SERIALIZABLE)
    failure = None
    try:
        before = expensive_count(t1)
        expensive_count(t2)

        t2.execute(insert(demo_items).values(name="Wine", price=500))
        t2.commit()  # T2 успевает зафиксироваться первой

        again = expensive_count(t1)  # призрака нет: T1 видит прежний снимок

        try:
            t1.execute(insert(demo_items).values(name="Beer", price=300))
            t1.commit()
        except DBAPIError as error:  # PostgreSQL отклоняет T1 при записи или при фиксации
            failure = type(error.orig).__name__
    finally:
        t1.close()
        t2.close()
    return Outcome(
        anomaly=again != before or failure is None,
        details=(
            f"T1 насчитала {before}; T2 добавила Wine(500) и зафиксировалась; T1 считает снова: {again}; "
            f"коммит T1 с вставкой на основании старого результата: "
            f"{'отклонен (' + failure + ')' if failure else 'прошел'}"
        ),
    )


# ---------------------------------------------------------------------------
# Список сценариев
# ---------------------------------------------------------------------------

PG_RU_NOTE = (
    "В PostgreSQL уровень READ UNCOMMITTED работает как READ COMMITTED: грязное чтение там "
    "невозможно ни на одном уровне (так это описано в документации)."
)
PG_PHANTOM_NOTE = (
    "REPEATABLE READ в PostgreSQL построен на снимках (snapshot isolation), поэтому призраков нет уже "
    "на этом уровне - это строже, чем требует стандарт SQL."
)

SCENARIOS = [
    Scenario(
        "1. Dirty read при READ UNCOMMITTED",
        "dirty read",
        READ_UNCOMMITTED,
        dirty_read(READ_UNCOMMITTED),
        {"mysql": True, "postgres": False},
        {"postgres": PG_RU_NOTE},
    ),
    Scenario(
        "2. Нет dirty read при READ COMMITTED",
        "dirty read",
        READ_COMMITTED,
        dirty_read(READ_COMMITTED),
        {"mysql": False, "postgres": False},
        {},
    ),
    Scenario(
        "3. Non-repeatable read при READ COMMITTED",
        "non-repeatable read",
        READ_COMMITTED,
        non_repeatable_read(READ_COMMITTED),
        {"mysql": True, "postgres": True},
        {},
    ),
    Scenario(
        "4. Нет non-repeatable read при REPEATABLE READ",
        "non-repeatable read",
        REPEATABLE_READ,
        non_repeatable_read(REPEATABLE_READ),
        {"mysql": False, "postgres": False},
        {},
    ),
    Scenario(
        "5. Phantom read при REPEATABLE READ",
        "phantom read",
        REPEATABLE_READ,
        phantom_read_repeatable_read,
        {"mysql": True, "postgres": False},
        {"postgres": PG_PHANTOM_NOTE},
    ),
    Scenario(
        "6. Нет phantom read при SERIALIZABLE",
        "phantom read",
        SERIALIZABLE,
        {"mysql": phantom_read_serializable_mysql, "postgres": phantom_read_serializable_postgres},
        {"mysql": False, "postgres": False},
        {},
    ),
]


def run_scenarios(engine: Engine, db: str) -> bool:
    rows = []
    all_as_expected = True

    for scenario in SCENARIOS:
        reset_table(engine)
        run = scenario.run[db] if isinstance(scenario.run, dict) else scenario.run
        outcome = run(engine)
        expected = scenario.expected[db]
        matches = outcome.anomaly == expected
        all_as_expected &= matches
        rows.append((scenario, outcome, expected, matches))

        print(f"\n{scenario.title}  [{scenario.level}]")
        print(f"  {outcome.details}")
        print(f"  аномалия {scenario.anomaly_name}: {'ЕСТЬ' if outcome.anomaly else 'нет'} "
              f"(ожидали: {'есть' if expected else 'нет'}) -> {'OK' if matches else 'НЕ СОВПАЛО'}")
        if db in scenario.note:
            print(f"  Примечание: {scenario.note[db]}")

    print(f"\n=== Итог ({db}) ===")
    print(f"{'Сценарий':<50} {'Уровень':<17} {'Аномалия':<10} Результат")
    for scenario, outcome, _, matches in rows:
        print(f"{scenario.title:<50} {scenario.level:<17} {'есть' if outcome.anomaly else 'нет':<10} "
              f"{'OK' if matches else 'НЕ СОВПАЛО'}")

    metadata.drop_all(engine, tables=[demo_items])
    return all_as_expected


def main() -> int:
    parser = argparse.ArgumentParser(description="Демонстрация уровней изоляции транзакций")
    parser.add_argument("--db", choices=sorted(DEFAULT_URLS), required=True)
    parser.add_argument("--url", help="строка подключения SQLAlchemy (по умолчанию - локальная БД из docker compose)")
    args = parser.parse_args()

    engine = create_engine(args.url or DEFAULT_URLS[args.db])
    ok = run_scenarios(engine, args.db)
    print("\nВсе сценарии совпали с ожиданием." if ok else "\nЕсть расхождения с ожиданием!")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
