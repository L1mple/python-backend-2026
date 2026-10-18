import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

URL = "postgresql+asyncpg://user:password@localhost:5432/shop_db"
engine = create_async_engine(URL)

async def main():
    print("--- PHANTOM READ (READ COMMITTED) ---")
    async with engine.connect() as conn_a:
        await conn_a.execute(text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED"))
        res1 = await conn_a.execute(text("SELECT COUNT(*) FROM items WHERE price > 500"))
        print(f"[A] Первое чтение (кол-во): {res1.scalar()}")

        async with engine.connect() as conn_b:
            await conn_b.execute(text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED"))
            await conn_b.execute(text("INSERT INTO items (name, price, deleted) VALUES ('Phantom1', 600, false)"))
            await conn_b.commit()
            print("[B] Добавил товар за 600")

        res2 = await conn_a.execute(text("SELECT COUNT(*) FROM items WHERE price > 500"))
        print(f"[A] Второе чтение (кол-во): {res2.scalar()}")
        print(">>> Phantom Read ПРОИЗОШЕЛ")

    print("\n--- PHANTOM READ (REPEATABLE READ в PostgreSQL) ---")
    async with engine.connect() as conn_a:
        await conn_a.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
        res1 = await conn_a.execute(text("SELECT COUNT(*) FROM items WHERE price > 500"))
        print(f"[A] Первое чтение (кол-во): {res1.scalar()}")

        async with engine.connect() as conn_b:
            await conn_b.execute(text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED"))
            await conn_b.execute(text("INSERT INTO items (name, price, deleted) VALUES ('Phantom2', 700, false)"))
            await conn_b.commit()
            print("[B] Добавил товар за 700")

        res2 = await conn_a.execute(text("SELECT COUNT(*) FROM items WHERE price > 500"))
        print(f"[A] Второе чтение (кол-во): {res2.scalar()}")
        print(">>> Phantom Read НЕ произошел (особенность PG)")

if __name__ == "__main__":
    asyncio.run(main())