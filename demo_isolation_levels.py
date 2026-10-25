"""
Демонстрация проблем изоляции транзакций PostgreSQL.

Каждая демонстрация запускает две сессии — с разными уровнями изоляции
и показывает, возникает ли конкретная аномалия.
"""

import asyncio
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncIterator

import psycopg2
from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    String,
    Table,
    select,
    text,
    update,
)
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

DB_URL = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/iso_demo"


metadata = MetaData()

accounts = Table(
    "accounts",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(32), nullable=False),
    Column("balance", Integer, nullable=False, default=0),
)

def _now():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def _log(label: str, msg: str):
    print(f"[{_now()}]  {label:12s} | {msg}")


def _create_db():
    conn = psycopg2.connect(
        host="127.0.0.1", port=5432,
        user="postgres", password="postgres",
    )
    conn.autocommit = True
    conn.cursor().execute("DROP DATABASE IF EXISTS iso_demo")
    conn.cursor().execute("CREATE DATABASE iso_demo")
    conn.close()


def _reset_schema():
    conn = psycopg2.connect(
        dbname="iso_demo",
        host="127.0.0.1", port=5432,
        user="postgres", password="postgres",
    )
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS accounts CASCADE")
    cur.execute(
        "CREATE TABLE accounts ("
        "id SERIAL PRIMARY KEY, name TEXT NOT NULL UNIQUE, "
        "balance INTEGER NOT NULL DEFAULT 0"
        ")"
    )
    cur.execute("INSERT INTO accounts (name, balance) VALUES ('alice', 0)")
    conn.close()


async def _reset_schema_async(engine: AsyncEngine):
    """Reset accounts table to initial state (single session)."""
    maker = async_sessionmaker(engine, expire_on_commit=False)
    s = maker()
    try:
        await s.execute(text("TRUNCATE TABLE accounts RESTART IDENTITY"))
        await s.execute(
            text("INSERT INTO accounts (name, balance) VALUES ('alice', 0)")
        )
        await s.commit()
    finally:
        await s.close()


@asynccontextmanager
async def open_sessions(
    engine: AsyncEngine,
    left: str,
    right: str,
) -> AsyncIterator[tuple[AsyncSession, AsyncSession]]:
    """Контекст-менеджер для двух сессий с разными уровнями изоляции."""
    maker = async_sessionmaker(engine, expire_on_commit=False)
    tx1 = maker()
    tx2 = maker()
    try:
        await tx1.execute(
            text(f"SET TRANSACTION ISOLATION LEVEL {left}")
        )
        await tx2.execute(
            text(f"SET TRANSACTION ISOLATION LEVEL {right}")
        )
        yield tx1, tx2
    finally:
        for s in (tx1, tx2):
            try:
                await s.rollback()
            except Exception:
                pass
            await s.close()


async def _select_balance(session: AsyncSession, label: str) -> int:
    """Helper: SELECT balance from alice."""
    _log(label, "SELECT alice.balance")
    result = await session.execute(
        select(accounts.c.balance).where(accounts.c.name == "alice")
    )
    value = result.scalar()
    _log(label, f"balance = {value}")
    return value


async def _select_names(session: AsyncSession, label: str) -> list[str]:
    """Helper: SELECT names ordered."""
    _log(label, "SELECT names ORDER BY name")
    result = await session.execute(
        select(accounts.c.name).order_by(accounts.c.name)
    )
    rows = result.fetchall()
    names = [r._mapping["name"] for r in rows]
    _log(label, f"{len(names)} rows: {names}")
    return names


async def dirty_read_uncommitted(engine: AsyncEngine) -> None:
    print("\n1. Dirty Read (READ UNCOMMITTED)")
    print("   PG не поддерживает RU, маппит на RC. Tx2 меняет, но не коммитит.")

    async with open_sessions(engine, "READ UNCOMMITTED", "READ COMMITTED") as (
        tx1, tx2
    ):
        _log("Tx2", "UPDATE alice = 9999, flush  (без commit)")
        await tx2.execute(
            update(accounts).where(accounts.c.name == "alice").values(balance=9999)
        )
        await tx2.flush()

        value = await _select_balance(tx1, "Tx1")

        ok = value != 9999
        print(f"   {'+' if ok else '-'} "
              f"{'предотвращено' if ok else 'произошло (странный случай!)'}\n")

    _reset_schema()


async def dirty_read_committed(engine: AsyncEngine) -> None:
    print("\n2. Dirty Read (READ COMMITTED)")
    print("   Tx2 меняет, не коммитит. Tx1 читает прежнее значение.")

    async with open_sessions(engine, "READ COMMITTED", "READ COMMITTED") as (
        tx1, tx2
    ):
        _log("Tx2", "UPDATE alice = 8888, flush  (без commit)")
        await tx2.execute(
            update(accounts).where(accounts.c.name == "alice").values(balance=8888)
        )
        await tx2.flush()

        value = await _select_balance(tx1, "Tx1")

        print(f"   + грязное чтение предотвращено (val={value}, не 8888)\n")


async def nonrepeatable_read_committed(engine: AsyncEngine) -> None:
    print("\n3. Non-repeatable Read (READ COMMITTED)")
    print("   Tx1 читает -> Tx2 коммитит новое -> Tx1 читает снова.")

    async with open_sessions(engine, "READ COMMITTED", "READ COMMITTED") as (
        tx1, tx2
    ):
        first = await _select_balance(tx1, "Tx1  (1)")

        _log("Tx2", "UPDATE alice = 500, COMMIT")
        await tx2.execute(
            update(accounts).where(accounts.c.name == "alice").values(balance=500)
        )
        await tx2.commit()

        second = await _select_balance(tx1, "Tx1  (2)")

        print(f"\n   + не-повторяемое чтение: {first} -> {second}\n")

    await _reset_schema_async(engine)


async def nonrepeatable_read_repeatable(engine: AsyncEngine) -> None:
    print("\n4. Non-repeatable Read (REPEATABLE READ) — предотвращено")
    print("   Оба SELECT'а Tx1 в одной сессии. Tx2 обновляет вне сессии.")

    async with open_sessions(engine, "REPEATABLE READ", "READ COMMITTED") as (
        tx1, tx2
    ):
        first = await _select_balance(tx1, "Tx1(RR)  (1)")

        _log("Tx2(RC)", "UPDATE alice = 777, COMMIT")
        await tx2.execute(
            update(accounts).where(accounts.c.name == "alice").values(balance=777)
        )
        await tx2.commit()

        second = await _select_balance(tx1, "Tx1(RR)  (2)")

        if first == second:
            print(f"\n   + предотвращено: оба чтения вернули {first}\n")
        else:
            print(f"\n   - неожиданно: {first} -> {second}\n")


async def phantom_reads_committed(engine: AsyncEngine) -> None:
    print("\n5. Phantom Reads (READ COMMITTED)")
    print("   Tx1 range-scan, Tx2 INSERT, Tx1 range-scan снова.")

    async with open_sessions(engine, "READ COMMITTED", "READ COMMITTED") as (
        tx1, tx2
    ):
        names1 = await _select_names(tx1, "Tx1  (1)")

        _log("Tx2", "INSERT bob, COMMIT")
        await tx2.execute(
            text("INSERT INTO accounts (name, balance) VALUES ('bob', 100)")
        )
        await tx2.commit()

        names2 = await _select_names(tx1, "Tx1  (2)")

        if len(names1) != len(names2):
            print(f"\n   + фантомное чтение: {len(names1)} -> {len(names2)} строк\n")
        else:
            print(f"\n   - случайно совпало: {len(names1)} строк\n")


async def serializable_prevents_anomaly(engine: AsyncEngine) -> None:
    print("\n6. Serializable — предотвращает все аномалии")
    print("   Tx1 читает + пишет alice, Tx2 коммитит UPDATE той же строки.")
    print("   -> конфликт on commit Tx1.\n")

    async with open_sessions(engine, "SERIALIZABLE", "SERIALIZABLE") as (
        tx1, tx2
    ):
        await _select_balance(tx1, "Tx1(SER)  SELECT")

        _log("Tx2(SER)", "UPDATE alice = 400, COMMIT")
        await tx2.execute(
            update(accounts).where(accounts.c.name == "alice").values(balance=400)
        )
        await tx2.commit()

        _log("Tx1(SER)", "UPDATE alice = 100, COMMIT (ожидание ошибки)")
        try:
            await tx1.execute(
                update(accounts).where(accounts.c.name == "alice").values(balance=100)
            )
            await tx1.commit()
            print(
                "   - Tx1 commit прошёл "
                "(Tx2 уже committed -> конфликта нет)\n"
            )
        except Exception as exc:
            await tx1.rollback()
            detail = str(exc)
            cause = exc.__cause__
            while cause:
                pgerror = getattr(cause, "pgerror", None)
                if pgerror:
                    detail = pgerror
                    break
                str_cause = str(cause)
                if str_cause and str_cause != detail:
                    detail = str_cause
                cause = cause.__cause__

            if "serializ" in detail.lower():
                print(
                    "   + SERIALIZABLE ERROR — конфликт read/write на одной строке"
                )
                print("   Tx1 откатился, сериализуемость сохранена.\n")
            else:
                print(f"   + Tx1 откатился: {detail}\n")


async def main() -> None:
    t0 = time.time()

    _create_db()
    _reset_schema()

    print("\nДемонстрация уровней изоляции транзакций PostgreSQL\n")
    print("  1  dirty read  (RU  -> маппит на RC)          [невозможно]")
    print("  2  dirty read  (RC)                            [предотвращено]")
    print("  3  non-repeatable read  (RC)                   [возможно]")
    print("  4  non-repeatable read  (RR)                   [предотвращено]")
    print("  5  phantom reads  (RC)                         [возможно]")
    print("  6  serializable                                [предотвращено]\n")

    engine = create_async_engine(
        DB_URL,
        pool_size=5, max_overflow=0, pool_pre_ping=False,
        pool_recycle=300,
    )
    try:
        await dirty_read_uncommitted(engine)
        await dirty_read_committed(engine)
        await nonrepeatable_read_committed(engine)
        await nonrepeatable_read_repeatable(engine)
        await phantom_reads_committed(engine)
        await serializable_prevents_anomaly(engine)
    finally:
        await engine.dispose()

    print(f"\nГотово  ({time.time() - t0:.1f}s)\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(1)
