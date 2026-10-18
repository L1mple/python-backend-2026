import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

URL = "postgresql+asyncpg://user:password@localhost:5432/shop_db"
engine = create_async_engine(URL)

async def main():
    print("--- NON-REPEATABLE READ (READ COMMITTED) ---")
    async with engine.connect() as conn_a:
        await conn_a.execute(text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED"))
        res1 = await conn_a.execute(text("SELECT price FROM items WHERE name = 'TestItem'"))
        print(f"[A] Первое чтение: {res1.scalar()}")

        async with engine.connect() as conn_b:
            await conn_b.execute(text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED"))
            await conn_b.execute(text("UPDATE items SET price = 300 WHERE name = 'TestItem'"))
            await conn_b.commit()
            print("[B] Обновил цену на 300")

        res2 = await conn_a.execute(text("SELECT price FROM items WHERE name = 'TestItem'"))
        print(f"[A] Второе чтение: {res2.scalar()}")
        print(">>> Non-repeatable Read ПРОИЗОШЕЛ")

    print("\n--- NON-REPEATABLE READ (REPEATABLE READ) ---")
    async with engine.connect() as conn_a:
        await conn_a.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
        res1 = await conn_a.execute(text("SELECT price FROM items WHERE name = 'TestItem'"))
        print(f"[A] Первое чтение: {res1.scalar()}")

        async with engine.connect() as conn_b:
            await conn_b.execute(text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED"))
            await conn_b.execute(text("UPDATE items SET price = 400 WHERE name = 'TestItem'"))
            await conn_b.commit()
            print("[B] Обновил цену на 400")

        res2 = await conn_a.execute(text("SELECT price FROM items WHERE name = 'TestItem'"))
        print(f"[A] Второе чтение: {res2.scalar()}")
        print(">>> Non-repeatable Read НЕ произошел")

if __name__ == "__main__":
    asyncio.run(main())