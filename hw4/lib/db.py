import contextlib
import os
from collections.abc import AsyncIterator

from fastapi import FastAPI
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

# Строка подключения
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@postgres:5432/master",
)

pool: AsyncConnectionPool | None = None

async def create_tables(pool: AsyncConnectionPool) -> None:
    async with pool.connection() as conn:
        async with conn.transaction():
            async with conn.cursor() as cursor:
                await cursor.execute('''
                    CREATE TABLE IF NOT EXISTS carts(
                        id SERIAL PRIMARY KEY
                    );
                    CREATE TABLE IF NOT EXISTS items(
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        price FLOAT NOT NULL,
                        deleted BOOLEAN NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS cart_items(
                        id SERIAL PRIMARY KEY,
                        item_id INTEGER REFERENCES items(id) NOT NULL,
                        cart_id INTEGER REFERENCES carts(id) NOT NULL,
                        quantity INTEGER NOT NULL
                    );
                    CREATE UNIQUE INDEX IF NOT EXISTS cart_item_unique_idx
                    ON cart_items (item_id, cart_id);
                    CREATE INDEX IF NOT EXISTS cart_id_idx
                    ON cart_items (cart_id);
                ''')


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    # [STARTUP] Этот код выполнится ДО того, как сервер начнет принимать запросы
    pool = AsyncConnectionPool(
        DATABASE_URL,
        min_size=1,
        max_size=20,
        open=False,
    )
    await pool.open(wait=True)

    try:
        await create_tables(pool)
        yield  # В этой точке приложение FastAPI работает и принимает запросы
    finally:
        # [SHUTDOWN] Этот код выполнится ПОСЛЕ того, как сервер остановится
        await pool.close()
        pool = None

# Функция-зависимость (Dependency) для эндпоинтов FastAPI
async def get_db_connection() -> AsyncIterator[AsyncConnection]:
    if pool is None:
        raise RuntimeError("Пул соединений базы данных не инициализирован.")
    async with pool.connection() as conn:
        yield conn
