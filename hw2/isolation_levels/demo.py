import asyncio, os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:password@localhost:7432/hw4_db",
)

engine = create_async_engine(DATABASE_URL, poolclass=NullPool)


class DemoTable:
    name = "isolation_demo"

    def __init__(self, _engine):
        self._engine = _engine

    async def reset(self) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(text(f"DROP TABLE IF EXISTS {self.name}"))
            await conn.execute(
                text(
                    f"CREATE TABLE {self.name} "
                    "(id integer PRIMARY KEY, value integer NOT NULL)"
                )
            )
            await conn.execute(
                text(f"INSERT INTO {self.name} (id, value) VALUES (1, 100), (2, 200)")
            )

    async def value(self, conn, row_id: int = 1):
        result = await conn.execute(
            text(f"SELECT value FROM {self.name} WHERE id = :row_id"),
            {"row_id": row_id},
        )
        return result.scalar()

    async def count(self, conn):
        result = await conn.execute(text(f"SELECT count(*) FROM {self.name}"))
        return result.scalar()


table = DemoTable(engine)


async def connect_at(level: str):
    conn = await engine.connect()
    await conn.execute(text(f"SET TRANSACTION ISOLATION LEVEL {level}"))
    return conn


async def run_dirty_read(writer_level: str, reader_level: str):
    await table.reset()
    writer = await connect_at(writer_level)
    reader = await connect_at(reader_level)
    try:
        await writer.execute(
            text(f"UPDATE {table.name} SET value = 999 WHERE id = 1")
        )
        observed = await table.value(reader, 1)
    finally:
        await writer.rollback()
        await writer.close()
        await reader.rollback()
        await reader.close()
    return observed


async def run_non_repeatable(reader_level: str):
    await table.reset()
    reader = await connect_at(reader_level)
    writer = await connect_at("READ COMMITTED")
    try:
        first = await table.value(reader, 1)
        await writer.execute(
            text(f"UPDATE {table.name} SET value = 999 WHERE id = 1")
        )
        await writer.commit()
        second = await table.value(reader, 1)
    finally:
        await reader.rollback()
        await reader.close()
        await writer.close()
    return first, second


async def run_phantom(reader_level: str):
    await table.reset()
    reader = await connect_at(reader_level)
    writer = await connect_at("READ COMMITTED")
    try:
        first = await table.count(reader)
        await writer.execute(
            text(f"INSERT INTO {table.name} (id, value) VALUES (3, 300)")
        )
        await writer.commit()
        second = await table.count(reader)
    finally:
        await reader.rollback()
        await reader.close()
        await writer.close()
    return first, second


def report(title: str, level: str, anomalous: bool, expected: bool, note: str) -> None:
    verdict = "аномалия ВОСПРОИЗВЕДЕНА" if anomalous else "аномалии НЕТ"
    match = "совпадает со стандартом" if anomalous == expected else "ОТЛИЧАЕТСЯ от стандарта"
    print(f"\n=== {title} @ {level} ===")
    print(f"  Ожидание (SQL) : {'есть аномалия' if expected else 'аномалии нет'}")
    print(f"  Факт           : {verdict}  ({match})")
    print(f"  Пояснение      : {note}")


async def main() -> None:
    print(f"База данных: PostgreSQL")

    observed = await run_dirty_read("READ UNCOMMITTED", "READ UNCOMMITTED")
    report(
        "Dirty read",
        "READ UNCOMMITTED",
        observed == 999,
        True,
        "PostgreSQL не поддерживает READ UNCOMMITTED и молча трактует его как "
        "READ COMMITTED, поэтому грязное чтение невозможно (читаем 100, а не 999). "
        "MySQL на этом уровне вернул бы 999.",
    )

    observed = await run_dirty_read("READ COMMITTED", "READ COMMITTED")
    report(
        "Dirty read",
        "READ COMMITTED",
        observed == 999,
        False,
        "Незакоммиченное изменение не видно второй транзакции — аномалия исключена.",
    )

    first, second = await run_non_repeatable("READ COMMITTED")
    report(
        "Non-repeatable read",
        "READ COMMITTED",
        first != second,
        True,
        f"Внутри одной транзакции значение изменилось {first} -> {second}.",
    )

    first, second = await run_non_repeatable("REPEATABLE READ")
    report(
        "Non-repeatable read",
        "REPEATABLE READ",
        first != second,
        False,
        f"Снимок данных зафиксирован, повторное чтение даёт {first} == {second}.",
    )

    first, second = await run_phantom("REPEATABLE READ")
    report(
        "Phantom read",
        "REPEATABLE READ",
        first != second,
        True,
        f"По стандарту фантом возможен, но PostgreSQL реализует REPEATABLE READ как "
        f"snapshot isolation, поэтому второй запрос снова видит {second} строк(и).",
    )

    first, second = await run_phantom("SERIALIZABLE")
    report(
        "Phantom read",
        "SERIALIZABLE",
        first != second,
        False,
        f"Сериализуемость исключает фантомы: {first} == {second}.",
    )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
