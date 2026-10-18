"""Сценарии аномалий транзакций на PostgreSQL.

Две транзакции (A и B) выполняются в одном процессе в заранее заданном порядке
на двух разных соединениях, поэтому результат детерминирован. Каждый сценарий
возвращает True, если аномалия *наблюдалась*.

Особенности PostgreSQL:
  * READ UNCOMMITTED ведет себя как READ COMMITTED, dirty read невозможен;
  * REPEATABLE READ реализован как snapshot isolation, phantom read невозможен.
Поэтому эти два сценария тут показывают отсутствие аномалии.
"""

from contextlib import contextmanager
from typing import Callable, Iterator

from sqlalchemy import Connection, text

from shop_api.store.db import engine

RU = "READ UNCOMMITTED"
RC = "READ COMMITTED"
RR = "REPEATABLE READ"
SER = "SERIALIZABLE"


@contextmanager
def transaction(level: str) -> Iterator[Connection]:
    with engine.connect().execution_options(isolation_level=level) as conn:
        with conn.begin():
            yield conn


def reset() -> None:
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS isolation_demo"))
        conn.execute(text("CREATE TABLE isolation_demo (id serial PRIMARY KEY, name text, price int)"))
        conn.execute(text("INSERT INTO isolation_demo (name, price) VALUES ('a', 100), ('b', 200)"))


def price_of_a(conn: Connection) -> int:
    return conn.execute(text("SELECT price FROM isolation_demo WHERE name = 'a'")).scalar_one()


def count_cheap(conn: Connection) -> int:
    return conn.execute(text("SELECT count(*) FROM isolation_demo WHERE price < 1000")).scalar_one()


def dirty_read(level: str) -> bool:
    """A видит незакоммиченное изменение B."""
    reset()
    with transaction(level) as a, transaction(level) as b:
        b.execute(text("UPDATE isolation_demo SET price = 999 WHERE name = 'a'"))
        seen = price_of_a(a)
        b.rollback()

    return seen == 999


def non_repeatable_read(level: str) -> bool:
    """Одно и то же чтение в A дает разное значение после коммита B."""
    reset()
    with transaction(level) as a:
        first = price_of_a(a)
        with transaction(RC) as b:
            b.execute(text("UPDATE isolation_demo SET price = 150 WHERE name = 'a'"))
        second = price_of_a(a)

    return first != second


def phantom_read(level: str) -> bool:
    """Повторный запрос по условию в A возвращает новые строки, добавленные B."""
    reset()
    with transaction(level) as a:
        first = count_cheap(a)
        with transaction(RC) as b:
            b.execute(text("INSERT INTO isolation_demo (name, price) VALUES ('c', 300)"))
        second = count_cheap(a)

    return first != second


# (описание, функция, ожидаемый результат на PostgreSQL, пояснение)
SCENARIOS: list[tuple[str, Callable[[], bool], bool, str]] = [
    ("dirty read при READ UNCOMMITTED", lambda: dirty_read(RU), False,
     "в PostgreSQL READ UNCOMMITTED == READ COMMITTED, не воспроизводится"),
    ("dirty read при READ COMMITTED", lambda: dirty_read(RC), False, ""),
    ("non-repeatable read при READ COMMITTED", lambda: non_repeatable_read(RC), True, ""),
    ("non-repeatable read при REPEATABLE READ", lambda: non_repeatable_read(RR), False, ""),
    ("phantom read при READ COMMITTED", lambda: phantom_read(RC), True, ""),
    ("phantom read при REPEATABLE READ", lambda: phantom_read(RR), False,
     "snapshot isolation в PostgreSQL не пропускает фантомов, не воспроизводится"),
    ("phantom read при SERIALIZABLE", lambda: phantom_read(SER), False, ""),
]
