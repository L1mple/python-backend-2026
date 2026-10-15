import asyncio
import os
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:password@localhost:5432/shop_db",
)

engine = create_async_engine(DATABASE_URL, echo=False, poolclass=NullPool)
SessionMaker = async_sessionmaker(engine, expire_on_commit=False)


async def reset_items() -> None:
    async with SessionMaker() as session:
        async with session.begin():
            await session.execute(text("DELETE FROM cart_items"))
            await session.execute(text("DELETE FROM items"))
            await session.execute(
                text("ALTER SEQUENCE items_id_seq RESTART WITH 1")
            )
            await session.execute(
                text("ALTER SEQUENCE cart_items_id_seq RESTART WITH 1")
            )
            await session.execute(
                text(
                    "INSERT INTO items (id, name, price, deleted) "
                    "VALUES (1, 'Item 1', 100.0, false)"
                )
            )


async def set_isolation_level(session: AsyncSession, level: str) -> None:
    allowed = {"READ UNCOMMITTED", "READ COMMITTED", "REPEATABLE READ", "SERIALIZABLE"}
    if level not in allowed:
        raise ValueError(f"Unsupported isolation level: {level}")
    await session.execute(text(f"SET TRANSACTION ISOLATION LEVEL {level}"))


async def actual_isolation_level(session: AsyncSession) -> str:
    result = await session.execute(text("SHOW transaction_isolation"))
    return str(result.scalar_one()).upper().replace("_", " ")


async def read_price(session: AsyncSession) -> float:
    result = await session.execute(
        text("SELECT price FROM items WHERE id = 1")
    )
    value = result.scalar_one()
    return float(value)


async def read_matching_ids(session: AsyncSession) -> list[int]:
    result = await session.execute(
        text("SELECT id FROM items WHERE price < 500.0 ORDER BY id")
    )
    return list(result.scalars().all())


def report(name: str, passed: bool, details: str = "") -> bool:
    status = "PASS" if passed else "FAIL"
    suffix = f" — {details}" if details else ""
    print(f"[{status}] {name}{suffix}")
    return passed


async def rollback_if_active(session: AsyncSession) -> None:
    """Откатывает транзакцию, если она ещё активна."""
    if session.in_transaction():
        await session.rollback()


# 1. Dirty read при запрошенном READ UNCOMMITTED
async def experiment_read_uncommitted() -> bool:
    print(" 1. Запрошен READ UNCOMMITTED: проверка dirty read")
    await reset_items()

    async with SessionMaker() as s1, SessionMaker() as s2:
        try:
            await s1.begin()
            await s2.begin()
            await set_isolation_level(s1, "READ UNCOMMITTED")
            await set_isolation_level(s2, "READ COMMITTED")

            actual = await actual_isolation_level(s1)
            print(f"Запрошенный уровень для s1: READ UNCOMMITTED")
            print(f"Фактический уровень PostgreSQL: {actual}")

            # s2 изменяет значение, но пока не фиксирует его.
            await s2.execute(
                text("UPDATE items SET price = 999.0 WHERE id = 1")
            )
            print("s2: UPDATE price = 999 (без COMMIT)")

            observed = await read_price(s1)
            print(f"s1 читает price = {observed}")

            # В PostgreSQL READ UNCOMMITTED отображается как READ COMMITTED.
            passed = actual in {"READ UNCOMMITTED", "READ COMMITTED",} and observed == 100.0
            return report(
                "Dirty read отсутствует при READ UNCOMMITTED в PostgreSQL",
                passed,
                f"SHOW вернул {actual}; незакоммиченное значение 999 не видно",
            )
        finally:
            await rollback_if_active(s1)
            await rollback_if_active(s2)


# 2. Нет dirty read при READ COMMITTED
async def experiment_no_dirty_read_read_committed() -> bool:
    print("2. Нет dirty read при READ COMMITTED")
    await reset_items()

    async with SessionMaker() as s1, SessionMaker() as s2:
        try:
            await s1.begin()
            await s2.begin()
            await set_isolation_level(s1, "READ COMMITTED")
            await set_isolation_level(s2, "READ COMMITTED")

            await s2.execute(
                text("UPDATE items SET price = 999.0 WHERE id = 1")
            )
            print("s2: UPDATE price = 999 (без COMMIT)")

            observed = await read_price(s1)
            print(f"s1 читает price = {observed}")

            return report(
                "Нет dirty read при READ COMMITTED",
                observed == 100.0,
                "прочитано старое зафиксированное значение 100",
            )
        finally:
            await rollback_if_active(s1)
            await rollback_if_active(s2)


# 3. Non-repeatable read при READ COMMITTED
async def experiment_non_repeatable_read_read_committed() -> bool:
    print(" 3. Non-repeatable read при READ COMMITTED")
    await reset_items()

    async with SessionMaker() as s1, SessionMaker() as s2:
        try:
            await s1.begin()
            await s2.begin()
            await set_isolation_level(s1, "READ COMMITTED")
            await set_isolation_level(s2, "READ COMMITTED")

            first = await read_price(s1)
            print(f"s1, первое чтение: {first}")

            await s2.execute(
                text("UPDATE items SET price = 999.0 WHERE id = 1")
            )
            await s2.commit()
            print("s2: UPDATE price = 999; COMMIT")

            second = await read_price(s1)
            print(f"s1, второе чтение: {second}")

            return report(
                "Non-repeatable read воспроизведён",
                first == 100.0 and second == 999.0,
                "один SELECT в транзакции вернул разные значения",
            )
        finally:
            await rollback_if_active(s1)
            await rollback_if_active(s2)


# 4. Нет non-repeatable read при REPEATABLE READ
async def experiment_no_non_repeatable_read_repeatable_read() -> bool:
    print("4. Нет non-repeatable read при REPEATABLE READ")
    await reset_items()

    async with SessionMaker() as s1, SessionMaker() as s2:
        try:
            await s1.begin()
            await s2.begin()
            await set_isolation_level(s1, "REPEATABLE READ")
            await set_isolation_level(s2, "READ COMMITTED")

            first = await read_price(s1)
            print(f"s1, первое чтение: {first}")

            await s2.execute(
                text("UPDATE items SET price = 999.0 WHERE id = 1")
            )
            await s2.commit()
            print("s2: UPDATE price = 999; COMMIT")

            second = await read_price(s1)
            print(f"s1, второе чтение: {second}")

            return report(
                "Non-repeatable read предотвращён",
                first == 100.0 and second == 100.0,
                "оба чтения видят один snapshot",
            )
        finally:
            await rollback_if_active(s1)
            await rollback_if_active(s2)


# 5. Проверка phantom read при REPEATABLE READ
async def experiment_phantom_read_repeatable_read() -> bool:
    print("5. Проверка phantom read при REPEATABLE READ")
    await reset_items()

    async with SessionMaker() as s1, SessionMaker() as s2:
        try:
            await s1.begin()
            await s2.begin()
            await set_isolation_level(s1, "REPEATABLE READ")
            await set_isolation_level(s2, "READ COMMITTED")

            first = await read_matching_ids(s1)
            print(f"s1, первое чтение ids: {first}")

            await s2.execute(
                text(
                    """
                    INSERT INTO items (id, name, price, deleted)
                    VALUES (2, 'Phantom', 50.0, false)
                    """
                )
            )
            await s2.commit()
            print("s2: INSERT id=2, price=50; COMMIT")

            second = await read_matching_ids(s1)
            print(f"s1, второе чтение ids: {second}")

            return report(
                "Phantom read отсутствует при PostgreSQL REPEATABLE READ",
                first == [1] and second == [1],
                "новая подходящая строка id=2 не видна в прежнем snapshot",
            )
        finally:
            await rollback_if_active(s1)
            await rollback_if_active(s2)


# 6. Нет phantom read при SERIALIZABLE
async def experiment_no_phantom_read_serializable() -> bool:
    print("6. Проверка phantom read при SERIALIZABLE")
    await reset_items()

    async with SessionMaker() as s1, SessionMaker() as s2:
        try:
            await s1.begin()
            await s2.begin()
            await set_isolation_level(s1, "SERIALIZABLE")
            await set_isolation_level(s2, "SERIALIZABLE")

            first = await read_matching_ids(s1)
            print(f"s1, первое чтение ids: {first}")

            await s2.execute(
                text(
                    """
                    INSERT INTO items (id, name, price, deleted)
                    VALUES (2, 'Phantom', 50.0, false)
                    """
                )
            )
            await s2.commit()
            print("s2: INSERT id=2, price=50; COMMIT")

            second = await read_matching_ids(s1)
            print(f"s1, второе чтение ids: {second}")

            # Фиксация read-only транзакции также проверяет, не возникла ли
            # ошибка сериализации при завершении транзакции.
            await s1.commit()

            return report(
                "Phantom read отсутствует при SERIALIZABLE",
                first == [1] and second == [1],
                "повторный SELECT видит прежний результат",
            )
        except DBAPIError as exc:
            await rollback_if_active(s1)
            await rollback_if_active(s2)
            sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
            if sqlstate == "40001":
                print("PostgreSQL прервал транзакцию из-за serialization failure (SQLSTATE 40001).")
                print("Для SERIALIZABLE это допустимый результат: приложение должно повторить транзакцию.")
                return report(
                    "SERIALIZABLE завершился допустимой ошибкой сериализации",
                    True,
                    "аномалия не принимается молча; требуется retry транзакции",
                )
            raise
        finally:
            await rollback_if_active(s1)
            await rollback_if_active(s2)


async def main() -> None:
    results: list[bool] = []
    try:
        results.append(await experiment_read_uncommitted())
        results.append(await experiment_no_dirty_read_read_committed())
        results.append(await experiment_non_repeatable_read_read_committed())
        results.append(await experiment_no_non_repeatable_read_repeatable_read())
        results.append(await experiment_phantom_read_repeatable_read())
        results.append(await experiment_no_phantom_read_serializable())
    finally:
        await engine.dispose()

    print("Итог")
    print(f"Успешно: {sum(results)} из {len(results)}")
    if not all(results):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
