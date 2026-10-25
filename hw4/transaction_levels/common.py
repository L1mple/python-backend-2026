from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import os

from psycopg import AsyncConnection, IsolationLevel


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@postgres:5432/master",
)


@asynccontextmanager
async def doctors_table() -> AsyncIterator[str]:
    table_name = "doctors"

    async with await AsyncConnection.connect(DATABASE_URL, autocommit=True) as conn:
        async with conn.cursor() as cur:
            await cur.execute(f"""
                CREATE TABLE {table_name}(
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    on_call BOOLEAN NOT NULL
                )
            """)
            await cur.execute(
                f"INSERT INTO {table_name}(id, name, on_call) VALUES "
                "(1, 'Alice', true), (2, 'Bob', true)"
            )

    try:
        yield table_name
    finally:
        async with await AsyncConnection.connect(DATABASE_URL, autocommit=True) as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"DROP TABLE IF EXISTS {table_name}")


def level_name(level: IsolationLevel) -> str:
    return level.name.replace("_", " ").title()


def level_sql(level: IsolationLevel) -> str:
    return level.name.replace("_", " ")


def log_sql(transaction: int, level: IsolationLevel, statement: str) -> None:
    print(f"T{transaction} ({level_name(level)}): {statement}")


def log_value(transaction: int, level: IsolationLevel, value: object) -> None:
    print(f"T{transaction} ({level_name(level)}): получил значение {value}")
