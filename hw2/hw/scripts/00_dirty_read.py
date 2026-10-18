import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

URL = "postgresql+asyncpg://user:password@localhost:5432/shop_db"
engine = create_async_engine(URL)


async def main():
    async with engine.connect() as conn:
        await conn.execute(
            text("INSERT INTO items (name, price, deleted) VALUES ('TestItem', 100, false) ON CONFLICT DO NOTHING"))
        await conn.commit()

    print("--- DIRTY READ (READ COMMITTED) ---")
    async with engine.connect() as conn_a:
        await conn_a.execute(text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED"))
        await conn_a.execute(text("UPDATE items SET price = 200 WHERE name = 'TestItem'"))
        print("[A] Обновил цену на 200 (без commit)")

        async with engine.connect() as conn_b:
            await conn_b.execute(text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED"))
            res = await conn_b.execute(text("SELECT price FROM items WHERE name = 'TestItem'"))
            print(f"[B] Прочитал цену: {res.scalar()}")
            print(">>> Dirty Read НЕ произошел (B не видит незакоммиченные данные)")

        await conn_a.rollback()


if __name__ == "__main__":
    asyncio.run(main())