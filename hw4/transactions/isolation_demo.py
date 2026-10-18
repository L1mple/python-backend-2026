"""PostgreSQL isolation experiments with two real simultaneous connections.

Run from the project root:
    docker compose run --rm api python transactions/isolation_demo.py

The experiments use a dedicated demo table, never the shop tables.
"""
import os
import threading
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

URL = os.getenv("DATABASE_URL", "postgresql+psycopg://shop:shop_dev_password@localhost:5432/shop")
engine = create_engine(URL)


def setup():
    with engine.begin() as c:
        c.execute(text("CREATE TABLE IF NOT EXISTS isolation_demo (id integer PRIMARY KEY, amount integer NOT NULL)"))
        c.execute(text("TRUNCATE isolation_demo"))
        c.execute(text("INSERT INTO isolation_demo (id, amount) VALUES (1, 100)"))


def dirty_read(level):
    setup()
    with engine.connect().execution_options(isolation_level=level) as a, \
         engine.connect().execution_options(isolation_level=level) as b:
        ta = a.begin()
        tb = b.begin()
        a.execute(text("UPDATE isolation_demo SET amount = 999 WHERE id = 1"))
        seen = b.scalar(text("SELECT amount FROM isolation_demo WHERE id = 1"))
        print(f"{level}: A updated but did not commit; B reads {seen} (100 means no dirty read)")
        assert seen == 100  # PostgreSQL maps READ UNCOMMITTED to READ COMMITTED
        ta.rollback()
        tb.rollback()


def non_repeatable(level, should_change):
    setup()
    with engine.connect().execution_options(isolation_level=level) as a, \
         engine.connect().execution_options(isolation_level=level) as b:
        ta = a.begin()
        before = a.scalar(text("SELECT amount FROM isolation_demo WHERE id = 1"))
        with b.begin():
            b.execute(text("UPDATE isolation_demo SET amount = 200 WHERE id = 1"))
        after = a.scalar(text("SELECT amount FROM isolation_demo WHERE id = 1"))
        ta.rollback()
        print(f"{level}: first read {before}, second read {after}")
        assert (before != after) == should_change


def phantom(level, should_change):
    setup()
    with engine.connect().execution_options(isolation_level=level) as a, \
         engine.connect().execution_options(isolation_level=level) as b:
        ta = a.begin()
        before = a.scalar(text("SELECT count(*) FROM isolation_demo WHERE amount >= 100"))
        with b.begin():
            b.execute(text("INSERT INTO isolation_demo (id, amount) VALUES (2, 300)"))
        after = a.scalar(text("SELECT count(*) FROM isolation_demo WHERE amount >= 100"))
        ta.rollback()
        print(f"{level}: matching rows {before} -> {after}")
        assert (before != after) == should_change


def serializable_write_skew():
    """Both transactions read 'at least one employee on duty' and remove one.

    PostgreSQL SERIALIZABLE's SSI must abort one transaction (SQLSTATE 40001).
    """
    with engine.begin() as c:
        c.execute(text("TRUNCATE isolation_demo"))
        c.execute(text("INSERT INTO isolation_demo (id, amount) VALUES (1, 1), (2, 1)"))

    barrier = threading.Barrier(2)
    outcomes = []
    lock = threading.Lock()

    def worker(employee_id):
        result = None
        with engine.connect().execution_options(isolation_level="SERIALIZABLE") as c:
            tx = c.begin()
            try:
                count = c.scalar(text("SELECT COUNT(*) FROM isolation_demo WHERE amount = 1"))
                assert count == 2
                barrier.wait(timeout=10)
                c.execute(text("UPDATE isolation_demo SET amount = 0 WHERE id = :id"), {"id": employee_id})
                tx.commit()
                result = "COMMITTED"
            except DBAPIError as exc:
                tx.rollback()
                if getattr(exc.orig, "sqlstate", None) != "40001":
                    raise
                result = "SERIALIZATION FAILURE (40001)"
            with lock:
                outcomes.append(result)

    threads = [threading.Thread(target=worker, args=(i,)) for i in (1, 2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    with engine.connect() as c:
        on_duty = c.scalar(text("SELECT COUNT(*) FROM isolation_demo WHERE amount = 1"))
    print(f"SERIALIZABLE write skew: {outcomes}; employees on duty: {on_duty}")
    assert sorted(outcomes) == ["COMMITTED", "SERIALIZATION FAILURE (40001)"]
    assert on_duty == 1


if __name__ == "__main__":
    if engine.dialect.name != "postgresql":
        raise RuntimeError("Use PostgreSQL to run isolation experiments")
    print("=== Dirty read ===")
    dirty_read("READ UNCOMMITTED")
    dirty_read("READ COMMITTED")
    print("=== Non-repeatable read ===")
    non_repeatable("READ COMMITTED", True)
    non_repeatable("REPEATABLE READ", False)
    print("=== Phantom read ===")
    phantom("READ COMMITTED", True)
    phantom("REPEATABLE READ", False)
    phantom("SERIALIZABLE", False)
    print("=== True serializable anomaly: write skew ===")
    serializable_write_skew()
    print("All experiments passed")
