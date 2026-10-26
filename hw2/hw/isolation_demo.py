import os
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, OperationalError


URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:password@127.0.0.1:7432/shop",
)

engine = create_engine(URL, pool_size=8, pool_pre_ping=True)


def setup():
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS iso_acc"))
        conn.execute(text("DROP TABLE IF EXISTS iso_goods"))
        conn.execute(text("CREATE TABLE iso_acc (id INT PRIMARY KEY, balance INT)"))
        conn.execute(text("CREATE TABLE iso_goods (id SERIAL PRIMARY KEY, price INT)"))
        conn.execute(text("INSERT INTO iso_acc (id, balance) VALUES (1, 100)"))


def open_tx(level):
    conn = engine.connect()
    conn = conn.execution_options(isolation_level=level)
    conn.begin()
    return conn


def close_tx(conn, commit=False):
    if conn.in_transaction():
        if commit:
            conn.commit()
        else:
            conn.rollback()
    conn.close()


def reset_acc(balance=100):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM iso_acc"))
        conn.execute(text("INSERT INTO iso_acc (id, balance) VALUES (1, :b)"), {"b": balance})


def reset_goods():
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM iso_goods"))


def balance(conn):
    return conn.execute(text("SELECT balance FROM iso_acc WHERE id = 1")).scalar()


def goods_count(conn, price):
    return conn.execute(
        text("SELECT COUNT(*) FROM iso_goods WHERE price = :p"),
        {"p": price},
    ).scalar()


def section(title):
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


def dirty_read():
    section("1. dirty read, READ UNCOMMITTED")
    reset_acc(100)
    writer = open_tx("READ UNCOMMITTED")
    reader = open_tx("READ UNCOMMITTED")
    level = reader.execute(text("SHOW transaction_isolation")).scalar()
    writer.execute(text("UPDATE iso_acc SET balance = 1 WHERE id = 1"))
    seen = balance(reader)
    print(f"SHOW transaction_isolation = {level}")
    print(f"писатель не закоммитил balance=1, читатель видит {seen}")
    close_tx(writer, commit=False)
    close_tx(reader, commit=False)
    if seen == 1:
        print("dirty read есть")
    else:
        print("dirty read нет: имя уровня read uncommitted, поведение как у read committed")


def no_dirty_read():
    section("2. нет dirty read, READ COMMITTED")
    reset_acc(100)
    writer = open_tx("READ COMMITTED")
    reader = open_tx("READ COMMITTED")
    writer.execute(text("UPDATE iso_acc SET balance = 1 WHERE id = 1"))
    seen = balance(reader)
    print(f"писатель не закоммитил balance=1, читатель видит {seen}")
    close_tx(writer, commit=False)
    close_tx(reader, commit=False)
    print("грязное значение не видно" if seen == 100 else "грязное значение просочилось")


def nonrepeatable():
    section("3. non-repeatable read, READ COMMITTED")
    reset_acc(100)
    reader = open_tx("READ COMMITTED")
    first = balance(reader)
    writer = open_tx("READ COMMITTED")
    writer.execute(text("UPDATE iso_acc SET balance = 80 WHERE id = 1"))
    close_tx(writer, commit=True)
    second = balance(reader)
    close_tx(reader, commit=False)
    print(f"первый select {first}, после чужого commit второй select {second}")
    print("строка поменялась внутри транзакции" if second == 80 else "не поменялась")


def no_nonrepeatable():
    section("4. нет non-repeatable read, REPEATABLE READ")
    reset_acc(100)
    reader = open_tx("REPEATABLE READ")
    first = balance(reader)
    writer = open_tx("READ COMMITTED")
    writer.execute(text("UPDATE iso_acc SET balance = 80 WHERE id = 1"))
    close_tx(writer, commit=True)
    second = balance(reader)
    close_tx(reader, commit=False)
    print(f"первый select {first}, после чужого commit второй select {second}")
    print("снимок держится" if second == 100 else "снимок не держится")


def phantom():
    section("5. phantom read, REPEATABLE READ")
    reset_goods()
    reader = open_tx("REPEATABLE READ")
    before = goods_count(reader, 10)
    writer = open_tx("READ COMMITTED")
    writer.execute(text("INSERT INTO iso_goods (price) VALUES (10)"))
    close_tx(writer, commit=True)
    after = goods_count(reader, 10)
    updated = reader.execute(text("UPDATE iso_goods SET price = 11 WHERE price = 10")).rowcount
    close_tx(reader, commit=False)
    print(f"до insert {before}, повторный select {after}, update зацепил {updated}")
    if after == 0 and updated == 0:
        print("фантома нет: у postgres repeatable read это snapshot, новые строки не видны")
    else:
        print("фантом проявился")


def no_phantom():
    section("6. SERIALIZABLE")
    reset_goods()
    a = open_tx("SERIALIZABLE")
    b = open_tx("SERIALIZABLE")
    ca = goods_count(a, 10)
    cb = goods_count(b, 10)
    a.execute(text("INSERT INTO iso_goods (price) VALUES (10)"))
    b.execute(text("INSERT INTO iso_goods (price) VALUES (10)"))
    close_tx(a, commit=True)
    failed = False
    try:
        close_tx(b, commit=True)
    except (OperationalError, DBAPIError) as e:
        failed = True
        print("второй commit отвергнут:", e.__class__.__name__)
        close_tx(b, commit=False)
    print(f"обе транзакции увидели {ca} и {cb} строк и обе вставили")
    if failed:
        print("фантом/аномалия не прошла: postgres откатил вторую транзакцию")
    else:
        print("оба commit прошли")


def main():
    print("url", URL)
    setup()
    dirty_read()
    no_dirty_read()
    nonrepeatable()
    no_nonrepeatable()
    phantom()
    no_phantom()
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
