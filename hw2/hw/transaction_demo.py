"""
Демонстрация аномалий транзакций и уровней изоляции через SQLAlchemy.

Запуск:
    docker compose exec shop-api python hw/transaction_demo.py

СУБД: PostgreSQL.
Особенности Postgres:
- READ UNCOMMITTED не поддерживается (мапится в READ COMMITTED).
- REPEATABLE READ использует Snapshot Isolation и предотвращает фантомы
  (в стандарте SQL на этом уровне фантомы допускаются).
"""

import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://shop_user:shop_password@localhost:5432/shop_db",
)

engine = create_engine(DATABASE_URL)


def make_session(isolation_level: str) -> Session:
    """Создаёт сессию с заданным уровнем изоляции."""
    return Session(engine, execution_options={"isolation_level": isolation_level})


def setup(conn):
    conn.execute(text("DROP TABLE IF EXISTS demo"))
    conn.execute(text("CREATE TABLE demo (id serial PRIMARY KEY, val int)"))
    conn.execute(text("INSERT INTO demo (val) VALUES (10)"))
    conn.commit()


def cleanup(conn):
    conn.execute(text("DROP TABLE IF EXISTS demo"))
    conn.commit()


def demo_dirty_read_ru():
    print("\n" + "=" * 60)
    print("DEMO 1: Dirty Read при READ UNCOMMITTED")
    print("=" * 60)
    print("  (Postgres не поддерживает RU — он работает как RC)")

    with engine.connect() as setup_conn:
        setup(setup_conn)

    s1 = make_session("READ UNCOMMITTED")
    s2 = make_session("READ UNCOMMITTED")
    try:
        s1.execute(text("UPDATE demo SET val = 20 WHERE id = 1"))
        # не коммитим

        val = s2.execute(text("SELECT val FROM demo WHERE id = 1")).scalar()
        print(f"  T1: UPDATE val=20, без commit")
        print(f"  T2: SELECT val = {val}")
        print(
            f"  → DIRTY READ {'OBSERVED' if val == 20 else 'NOT OBSERVED (Postgres: RU → RC)'}"
        )
        s1.rollback()
    finally:
        s1.close()
        s2.close()


def demo_no_dirty_read_rc():
    print("\n" + "=" * 60)
    print("DEMO 2: Dirty Read при READ COMMITTED (должен быть предотвращён)")
    print("=" * 60)

    with engine.connect() as setup_conn:
        setup(setup_conn)

    s1 = make_session("READ COMMITTED")
    s2 = make_session("READ COMMITTED")
    try:
        s1.execute(text("UPDATE demo SET val = 20 WHERE id = 1"))

        val = s2.execute(text("SELECT val FROM demo WHERE id = 1")).scalar()
        print(f"  T1: UPDATE val=20, без commit")
        print(f"  T2: SELECT val = {val}")
        print(f"  → DIRTY READ {'OBSERVED' if val == 20 else 'NOT OBSERVED'}")
        s1.rollback()
    finally:
        s1.close()
        s2.close()


def demo_non_repeatable_read_rc():
    print("\n" + "=" * 60)
    print("DEMO 3: Non-repeatable Read при READ COMMITTED (должен наблюдаться)")
    print("=" * 60)

    with engine.connect() as setup_conn:
        setup(setup_conn)

    s1 = make_session("READ COMMITTED")
    s2 = make_session("READ COMMITTED")
    try:
        val1 = s2.execute(text("SELECT val FROM demo WHERE id = 1")).scalar()

        s1.execute(text("UPDATE demo SET val = 30 WHERE id = 1"))
        s1.commit()

        val2 = s2.execute(text("SELECT val FROM demo WHERE id = 1")).scalar()

        print(f"  T2 первый SELECT: {val1}")
        print(f"  T1 UPDATE val=30 + commit")
        print(f"  T2 второй SELECT: {val2}")
        print(
            f"  → NON-REPEATABLE READ {'OBSERVED' if val1 != val2 else 'NOT OBSERVED'}"
        )
        s2.rollback()
    finally:
        s1.close()
        s2.close()


def demo_no_non_repeatable_read_rr():
    print("\n" + "=" * 60)
    print("DEMO 4: Non-repeatable Read при REPEATABLE READ (должен быть предотвращён)")
    print("=" * 60)

    with engine.connect() as setup_conn:
        setup(setup_conn)

    s1 = make_session("REPEATABLE READ")
    s2 = make_session("REPEATABLE READ")
    try:
        val1 = s2.execute(text("SELECT val FROM demo WHERE id = 1")).scalar()

        s1.execute(text("UPDATE demo SET val = 30 WHERE id = 1"))
        s1.commit()

        val2 = s2.execute(text("SELECT val FROM demo WHERE id = 1")).scalar()

        print(f"  T2 первый SELECT: {val1}")
        print(f"  T1 UPDATE val=30 + commit")
        print(f"  T2 второй SELECT: {val2}")
        print(
            f"  → NON-REPEATABLE READ {'NOT OBSERVED' if val1 == val2 else 'OBSERVED'}"
        )
        s2.rollback()
    finally:
        s1.close()
        s2.close()


def demo_phantom_read_rr():
    print("\n" + "=" * 60)
    print("DEMO 5: Phantom Read при REPEATABLE READ")
    print("=" * 60)
    print("  (В стандарте SQL RR допускает фантомы, но Postgres предотвращает)")

    with engine.connect() as setup_conn:
        setup(setup_conn)

    s1 = make_session("REPEATABLE READ")
    s2 = make_session("REPEATABLE READ")
    try:
        c1 = s2.execute(text("SELECT COUNT(*) FROM demo")).scalar()

        s1.execute(text("INSERT INTO demo (val) VALUES (99)"))
        s1.commit()

        c2 = s2.execute(text("SELECT COUNT(*) FROM demo")).scalar()

        print(f"  T2 первый COUNT: {c1}")
        print(f"  T1 INSERT + commit")
        print(f"  T2 второй COUNT: {c2}")
        print(
            f"  → PHANTOM READ {'NOT OBSERVED (snapshot isolation в Postgres)' if c1 == c2 else 'OBSERVED'}"
        )
        s2.rollback()
    finally:
        s1.close()
        s2.close()


def demo_no_phantom_read_serializable():
    print("\n" + "=" * 60)
    print("DEMO 6: Phantom Read при SERIALIZABLE (должен быть предотвращён)")
    print("=" * 60)

    with engine.connect() as setup_conn:
        setup(setup_conn)

    s1 = make_session("SERIALIZABLE")
    s2 = make_session("SERIALIZABLE")
    try:
        c1 = s2.execute(text("SELECT COUNT(*) FROM demo")).scalar()

        s1.execute(text("INSERT INTO demo (val) VALUES (99)"))
        s1.commit()

        c2 = s2.execute(text("SELECT COUNT(*) FROM demo")).scalar()

        print(f"  T2 первый COUNT: {c1}")
        print(f"  T1 INSERT + commit")
        print(f"  T2 второй COUNT: {c2}")
        print(f"  → PHANTOM READ {'NOT OBSERVED' if c1 == c2 else 'OBSERVED'}")
        s2.rollback()
    finally:
        s1.close()
        s2.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Демонстрация аномалий транзакций и уровней изоляции (SQLAlchemy)")
    print("СУБД: PostgreSQL")
    print("=" * 60)

    demo_dirty_read_ru()
    demo_no_dirty_read_rc()
    demo_non_repeatable_read_rc()
    demo_no_non_repeatable_read_rr()
    demo_phantom_read_rr()
    demo_no_phantom_read_serializable()

    print("\n" + "=" * 60)
    print("Готово.")
    print("=" * 60)
