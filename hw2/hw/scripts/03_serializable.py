import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.exc import DBAPIError

URL = "postgresql+asyncpg://user:password@localhost:5432/shop_db"
engine = create_async_engine(URL)

async def main():
    print("--- SERIALIZABLE (Защита от конфликтов) ---")
    async with engine.connect() as conn_a:
        await conn_a.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
        res = await conn_a.execute(text("SELECT price FROM items WHERE name = 'TestItem'"))
        print(f"[A] Прочитал цену: {res.scalar()}")

        async with engine.connect() as conn_b:
            await conn_b.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
            await conn_b.execute(text("UPDATE items SET price = 800 WHERE name = 'TestItem'"))
            await conn_b.commit()
            print("[B] Обновил цену на 800")

        try:
            await conn_a.execute(text("UPDATE items SET price = 900 WHERE name = 'TestItem'"))
            await conn_a.commit()
            print("[A] Успешно обновил цену.")
        except DBAPIError:
            print("[A] Ошибка сериализации! Транзакция A отменена СУБД.")

if __name__ == "__main__":
    asyncio.run(main())