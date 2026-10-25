"""Демонстрация аномалий транзакций и уровней изоляции через SQLAlchemy.

Запуск:
    python isolation_demo.py postgres
    python isolation_demo.py mysql
    python isolation_demo.py          # обе БД подряд

Две транзакции (T1, T2) = два соединения, шаги чередуются в одном потоке,
поэтому порядок событий детерминирован. Вердикт каждого сценария считается
по реально прочитанным значениям, а не зашит в текст.
"""
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

URLS = {
    "postgres": "postgresql+psycopg2://postgres:password@localhost:7432/shop",
    "mysql": "mysql+pymysql://root:password@localhost:7306/hw4_db",
}


def reset(url: str) -> None:
    eng = create_engine(url, poolclass=NullPool)
    with eng.begin() as c:
        c.execute(text("DROP TABLE IF EXISTS accounts"))
        c.execute(text("DROP TABLE IF EXISTS products"))
        c.execute(text("CREATE TABLE accounts (id INT PRIMARY KEY, balance INT NOT NULL)"))
        c.execute(text("CREATE TABLE products (id INT PRIMARY KEY, name VARCHAR(50), price INT NOT NULL)"))
        c.execute(text("INSERT INTO accounts VALUES (1, 100)"))
        c.execute(text("INSERT INTO products VALUES (1, 'A', 150), (2, 'B', 200), (3, 'C', 50)"))


def two_conns(url: str, level: str):
    """Два независимых соединения с одним и тем же уровнем изоляции."""
    eng = create_engine(url, isolation_level=level, poolclass=NullPool)
    c1, c2 = eng.connect(), eng.connect()
    # чтобы блокировки не вешали скрипт навсегда
    lock_sql = (
        "SET lock_timeout = '2s'" if eng.dialect.name == "postgresql"
        else "SET SESSION innodb_lock_wait_timeout = 2"
    )
    c2.execute(text(lock_sql))
    c2.rollback()
    return c1, c2


def scalar(conn, sql):
    return conn.execute(text(sql)).scalar()


def verdict(title: str, level: str, anomaly: bool, detail: str, expect_anomaly: bool) -> None:
    mark = "АНОМАЛИЯ ЕСТЬ" if anomaly else "аномалии нет"
    ok = "" if anomaly == expect_anomaly else "  <-- не совпало с ожиданием для этой СУБД, см. комментарий в README"
    print(f"[{level:16}] {title}: {mark}. {detail}{ok}")


# ---------- dirty read ----------
def dirty_read(url, level, expect):
    reset(url)
    c1, c2 = two_conns(url, level)
    try:
        c1.execute(text("UPDATE accounts SET balance = 0 WHERE id = 1"))  # без commit
        seen = scalar(c2, "SELECT balance FROM accounts WHERE id = 1")
        c1.rollback()
        verdict("dirty read", level, seen == 0,
                f"T1 записал 0 и откатил; T2 прочитал {seen} (в БД на самом деле 100)", expect)
    finally:
        c1.close(); c2.close()


# ---------- non-repeatable read ----------
def non_repeatable(url, level, expect):
    reset(url)
    c1, c2 = two_conns(url, level)
    try:
        first = scalar(c1, "SELECT balance FROM accounts WHERE id = 1")
        c2.execute(text("UPDATE accounts SET balance = 500 WHERE id = 1"))
        c2.commit()
        second = scalar(c1, "SELECT balance FROM accounts WHERE id = 1")
        verdict("non-repeatable read", level, first != second,
                f"T1 прочитал {first}, T2 закоммитил 500, T1 прочитал снова {second}", expect)
    finally:
        c1.close(); c2.close()


# ---------- phantom read ----------
def phantom(url, level, expect):
    reset(url)
    c1, c2 = two_conns(url, level)
    q = "SELECT COUNT(*) FROM products WHERE price > 100"
    try:
        before = scalar(c1, q)
        blocked = False
        try:
            c2.execute(text("INSERT INTO products VALUES (4, 'D', 300)"))
            c2.commit()
        except DBAPIError:
            c2.rollback()
            blocked = True  # T2 упёрся в блокировку T1 (так делает MySQL на SERIALIZABLE)
        plain = scalar(c1, q)
        # Обычный SELECT в снимке фантом не покажет. Но если T1 теперь ИЗМЕНЯЕТ
        # строки по тому же предикату, InnoDB «видит» новую строку.
        upd = c1.execute(text("UPDATE products SET price = price + 1 WHERE price > 100"))
        touched = upd.rowcount
        after = scalar(c1, q)
        c1.commit()
        anomaly = (not blocked) and (after != before)
        if blocked:
            detail = f"T1 читал count={before}; INSERT в T2 заблокирован (lock timeout) -> строка не появилась"
        else:
            detail = (f"count до={before}, обычный SELECT после вставки T2={plain}, "
                      f"UPDATE затронул {touched} строк, count после UPDATE={after}")
        verdict("phantom read", level, anomaly, detail, expect)
    except DBAPIError as e:
        # Postgres SERIALIZABLE может отменить транзакцию при конфликте
        print(f"[{level:16}] phantom read: транзакция отменена СУБД ({type(e.orig).__name__}) -> аномалия невозможна")
    finally:
        c1.close(); c2.close()


def run(name: str) -> None:
    url = URLS[name]
    pg = name == "postgres"
    print(f"\n===== {name} =====")
    # (функция, уровень, ожидаем аномалию?)
    dirty_read(url, "READ UNCOMMITTED", expect=not pg)   # PG: RU работает как RC
    dirty_read(url, "READ COMMITTED", expect=False)
    non_repeatable(url, "READ COMMITTED", expect=True)
    non_repeatable(url, "REPEATABLE READ", expect=False)
    phantom(url, "REPEATABLE READ", expect=not pg)        # PG: снимок -> фантомов нет
    phantom(url, "SERIALIZABLE", expect=False)


if __name__ == "__main__":
    for db in (sys.argv[1:] or ["postgres", "mysql"]):
        run(db)