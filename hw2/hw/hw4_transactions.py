"""
Демонстрация проблем транзакций и уровней изоляции на PostgreSQL.

Запуск (при поднятом PostgreSQL из docker-compose):

    export DATABASE_URL="postgresql+asyncpg://shop_user:shop_password@localhost:5433/shop_db"
    python hw4_transactions.py
"""

import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://shop_user:shop_password@localhost:5433/shop_db",
)


async def setup(engine) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS accounts"))
        await conn.execute(
            text("CREATE TABLE accounts (id SERIAL PRIMARY KEY, balance INT)")
        )
        await conn.execute(
            text("INSERT INTO accounts (id, balance) VALUES (1, 100)")
        )


async def demo_dirty_read(engine) -> None:
    print("\n=== 1. Dirty Read (грязное чтение) ===")
    await setup(engine)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as a, Session() as b:
        await a.execute(text("BEGIN"))
        await a.execute(
            text("UPDATE accounts SET balance = 1000 WHERE id = 1")
        )
        print("A: UPDATE balance = 1000 (не закоммичено)")

        await b.execute(
            text("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
        )
        result = await b.execute(
            text("SELECT balance FROM accounts WHERE id = 1")
        )
        balance = result.scalar()
        print(f"B (READ UNCOMMITTED): SELECT balance -> {balance}")

        if balance == 100:
            print(
                "OK: грязного чтения НЕТ (PostgreSQL не поддерживает READ UNCOMMITTED,"
            )
            print(
                "    ведёт себя как READ COMMITTED). Это корректное поведение."
            )
        else:
            print("FAIL: грязное чтение произошло!")

        await a.rollback()
        await b.rollback()


async def demo_non_repeatable_read(engine) -> None:
    print("\n=== 2. Non-repeatable Read (неповторяющееся чтение) ===")
    Session = async_sessionmaker(engine, expire_on_commit=False)

    await setup(engine)
    async with Session() as a, Session() as b:
        print("\n>>> READ COMMITTED")
        await a.execute(text("BEGIN"))
        await a.execute(text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED"))
        r1 = (
            await a.execute(text("SELECT balance FROM accounts WHERE id = 1"))
        ).scalar()
        print(f"A: первое чтение  = {r1}")

        await b.execute(text("BEGIN"))
        await b.execute(text("UPDATE accounts SET balance = 200 WHERE id = 1"))
        await b.commit()
        print("B: UPDATE balance = 200 + COMMIT")

        r2 = (
            await a.execute(text("SELECT balance FROM accounts WHERE id = 1"))
        ).scalar()
        print(f"A: второе чтение  = {r2}")
        if r1 != r2:
            print(
                "OK: Non-repeatable Read ПРОИЗОШЁЛ (ожидаемо для READ COMMITTED)"
            )
        else:
            print("FAIL: Non-repeatable Read не произошёл")
        await a.rollback()

    await setup(engine)
    async with Session() as a, Session() as b:
        print("\n>>> REPEATABLE READ")
        await a.execute(text("BEGIN"))
        await a.execute(
            text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        )
        r1 = (
            await a.execute(text("SELECT balance FROM accounts WHERE id = 1"))
        ).scalar()
        print(f"A: первое чтение  = {r1}")

        await b.execute(text("BEGIN"))
        await b.execute(text("UPDATE accounts SET balance = 300 WHERE id = 1"))
        await b.commit()
        print("B: UPDATE balance = 300 + COMMIT")

        r2 = (
            await a.execute(text("SELECT balance FROM accounts WHERE id = 1"))
        ).scalar()
        print(f"A: второе чтение  = {r2}")
        if r1 == r2:
            print("OK: Non-repeatable Read НЕТ (ожидаемо для REPEATABLE READ)")
        else:
            print("FAIL: Non-repeatable Read произошёл")
        await a.rollback()


async def demo_phantom_read(engine) -> None:
    print("\n=== 3. Phantom Read (фантомное чтение) ===")
    Session = async_sessionmaker(engine, expire_on_commit=False)

    await setup(engine)
    async with Session() as a, Session() as b:
        print("\n>>> READ COMMITTED")
        await a.execute(text("BEGIN"))
        await a.execute(text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED"))
        c1 = (
            await a.execute(
                text("SELECT COUNT(*) FROM accounts WHERE balance > 50")
            )
        ).scalar()
        print(f"A: первое COUNT(*) = {c1}")

        await b.execute(text("BEGIN"))
        await b.execute(
            text("INSERT INTO accounts (id, balance) VALUES (2, 100)")
        )
        await b.commit()
        print("B: INSERT (id=2, balance=100) + COMMIT")

        c2 = (
            await a.execute(
                text("SELECT COUNT(*) FROM accounts WHERE balance > 50")
            )
        ).scalar()
        print(f"A: второе COUNT(*) = {c2}")
        if c1 != c2:
            print("OK: Phantom Read ПРОИЗОШЁЛ (ожидаемо для READ COMMITTED)")
        else:
            print("FAIL: Phantom Read не произошёл")
        await a.rollback()

    await setup(engine)
    async with Session() as a, Session() as b:
        print("\n>>> REPEATABLE READ (PostgreSQL)")
        await a.execute(text("BEGIN"))
        await a.execute(
            text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        )
        c1 = (
            await a.execute(
                text("SELECT COUNT(*) FROM accounts WHERE balance > 50")
            )
        ).scalar()
        print(f"A: первое COUNT(*) = {c1}")

        await b.execute(text("BEGIN"))
        await b.execute(
            text("INSERT INTO accounts (id, balance) VALUES (3, 150)")
        )
        await b.commit()
        print("B: INSERT (id=3, balance=150) + COMMIT")

        c2 = (
            await a.execute(
                text("SELECT COUNT(*) FROM accounts WHERE balance > 50")
            )
        ).scalar()
        print(f"A: второе COUNT(*) = {c2}")
        if c1 == c2:
            print(
                "OK: Phantom Read НЕТ (PostgreSQL REPEATABLE READ = snapshot isolation)"
            )
        else:
            print("FAIL: Phantom Read произошёл")
        await a.rollback()

    await setup(engine)
    async with Session() as a, Session() as b:
        print("\n>>> SERIALIZABLE")
        await a.execute(text("BEGIN"))
        await a.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
        c1 = (
            await a.execute(
                text("SELECT COUNT(*) FROM accounts WHERE balance > 50")
            )
        ).scalar()
        print(f"A: первое COUNT(*) = {c1}")

        await b.execute(text("BEGIN"))
        await b.execute(
            text("INSERT INTO accounts (id, balance) VALUES (4, 200)")
        )
        await b.commit()
        print("B: INSERT (id=4, balance=200) + COMMIT")

        c2 = (
            await a.execute(
                text("SELECT COUNT(*) FROM accounts WHERE balance > 50")
            )
        ).scalar()
        print(f"A: второе COUNT(*) = {c2}")
        if c1 == c2:
            print("OK: Phantom Read НЕТ (ожидаемо для SERIALIZABLE)")
        else:
            print("FAIL: Phantom Read произошёл")
        await a.rollback()


async def main() -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)
    try:
        await demo_dirty_read(engine)
        await demo_non_repeatable_read(engine)
        await demo_phantom_read(engine)
    finally:
        await engine.dispose()
    print("\nГотово.")


if __name__ == "__main__":
    asyncio.run(main())
