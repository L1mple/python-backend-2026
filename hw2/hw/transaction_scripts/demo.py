import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:password@localhost:7432/hw4_db",
)

engine = create_async_engine(DATABASE_URL, echo=False, poolclass=NullPool)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def reset_product_price(price: float = 100.0) -> None:
    """Сбросить цену первого товара — чтобы демо были воспроизводимы."""
    async with async_session() as s:
        await s.execute(
            text("UPDATE products SET price = :p WHERE id = 1"),
            {"p": price},
        )
        await s.commit()


async def demo_dirty_read() -> None:
    print("\n" + "=" * 70)
    print("1. Dirty read при READ UNCOMMITTED")
    print("=" * 70)
    print("Пытаемся прочитать незакоммиченные данные из другой транзакции.")
    print("PostgreSQL НЕ поддерживает READ UNCOMMITTED — он молча")
    print("апгрейдит уровень до READ COMMITTED. Поэтому dirty read")
    print("невозможен в принципе.\n")

    await reset_product_price(100.0)

    s1 = async_session()
    s2 = async_session()
    try:
        await s1.execute(text("BEGIN"))
        await s1.execute(text("UPDATE products SET price = 1111.11 WHERE id = 1"))
        print("Сессия 1: UPDATE price = 1111.11 (без COMMIT)")

        await s2.execute(text("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED"))
        await s2.execute(text("BEGIN"))
        result = await s2.execute(text("SELECT price FROM products WHERE id = 1"))
        price = float(result.scalar_one())
        print(f"Сессия 2 (READ UNCOMMITTED) прочитала price = {price}")
        print(f"  -> Ожидалось бы 1111.11 при настоящем dirty read")
        print(f"  -> Получили {price} — dirty read НЕ происходит")

        await s1.execute(text("ROLLBACK"))
        await s2.execute(text("ROLLBACK"))
    finally:
        await s1.close()
        await s2.close()


async def demo_no_dirty_read_read_committed() -> None:
    print("\n" + "=" * 70)
    print("2. Нет dirty read при READ COMMITTED")
    print("=" * 70)
    print("Та же ситуация, но уровень READ COMMITTED явно.")
    print("Незакоммиченные данные по-прежнему не видны.\n")

    await reset_product_price(100.0)

    s1 = async_session()
    s2 = async_session()
    try:
        await s1.execute(text("BEGIN"))
        await s1.execute(text("UPDATE products SET price = 2222.22 WHERE id = 1"))
        print("Сессия 1: UPDATE price = 2222.22 (без COMMIT)")

        await s2.execute(text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED"))
        await s2.execute(text("BEGIN"))
        result = await s2.execute(text("SELECT price FROM products WHERE id = 1"))
        price = float(result.scalar_one())
        print(f"Сессия 2 (READ COMMITTED) прочитала price = {price}")
        print(f"  -> Ожидалось {2222.22} при dirty read")
        print(f"  -> Получили {price} — dirty read НЕ происходит")

        await s1.execute(text("ROLLBACK"))
        await s2.execute(text("ROLLBACK"))
    finally:
        await s1.close()
        await s2.close()


async def demo_non_repeatable_read() -> None:
    print("\n" + "=" * 70)
    print("3. Non-repeatable read при READ COMMITTED")
    print("=" * 70)
    print("Сессия 1 читает значение дважды в одной транзакции.")
    print("Между чтениями сессия 2 меняет и коммитит.")
    print("При READ COMMITTED второе чтение увидит новое значение.\n")

    await reset_product_price(100.0)

    s1 = async_session()
    s2 = async_session()
    try:
        await s1.execute(text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED"))
        await s1.execute(text("BEGIN"))

        result = await s1.execute(text("SELECT price FROM products WHERE id = 1"))
        first = float(result.scalar_one())
        print(f"Сессия 1, первое чтение: price = {first}")

        await s2.execute(text("BEGIN"))
        await s2.execute(text("UPDATE products SET price = 3333.33 WHERE id = 1"))
        await s2.execute(text("COMMIT"))
        print("Сессия 2: UPDATE price = 3333.33 + COMMIT")

        result = await s1.execute(text("SELECT price FROM products WHERE id = 1"))
        second = float(result.scalar_one())
        print(f"Сессия 1, второе чтение: price = {second}")

        if first != second:
            print(f"  -> NON-REPEATABLE READ воспроизведён: {first} != {second}")
        else:
            print(f"  -> Аномалии нет: {first} == {second}")

        await s1.execute(text("ROLLBACK"))
    finally:
        await s1.close()
        await s2.close()


async def demo_no_non_repeatable_read() -> None:
    print("\n" + "=" * 70)
    print("4. Нет non-repeatable read при REPEATABLE READ")
    print("=" * 70)
    print("Та же ситуация, но уровень REPEATABLE READ.")
    print("PostgreSQL использует snapshot isolation — второе чтение")
    print("видит тот же снимок, что и первое.\n")

    await reset_product_price(100.0)

    s1 = async_session()
    s2 = async_session()
    try:
        await s1.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
        await s1.execute(text("BEGIN"))

        result = await s1.execute(text("SELECT price FROM products WHERE id = 1"))
        first = float(result.scalar_one())
        print(f"Сессия 1, первое чтение: price = {first}")

        await s2.execute(text("BEGIN"))
        await s2.execute(text("UPDATE products SET price = 4444.44 WHERE id = 1"))
        await s2.execute(text("COMMIT"))
        print("Сессия 2: UPDATE price = 4444.44 + COMMIT")

        result = await s1.execute(text("SELECT price FROM products WHERE id = 1"))
        second = float(result.scalar_one())
        print(f"Сессия 1, второе чтение: price = {second}")

        if first == second:
            print(f"  -> Аномалии НЕТ: {first} == {second} (snapshot isolation работает)")
        else:
            print(f"  -> Аномалия: {first} != {second}")

        await s1.execute(text("ROLLBACK"))
    finally:
        await s1.close()
        await s2.close()


async def demo_phantom_read() -> None:
    print("\n" + "=" * 70)
    print("5. Phantom reads при REPEATABLE READ")
    print("=" * 70)
    print("Сессия 1 дважды считает количество строк с условием.")
    print("Сессия 2 вставляет новую подходящую строку и коммитит.")
    print("PostgreSQL на REPEATABLE READ использует snapshot isolation,")
    print("поэтому фантомов тоже НЕТ (строже, чем требует стандарт).\n")

    async with async_session() as s:
        await s.execute(text("DELETE FROM products WHERE name LIKE 'phantom-%'"))
        await s.commit()

    s1 = async_session()
    s2 = async_session()
    try:
        await s1.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
        await s1.execute(text("BEGIN"))

        result = await s1.execute(
            text("SELECT COUNT(*) FROM products WHERE name LIKE 'phantom-%'")
        )
        first = int(result.scalar_one())
        print(f"Сессия 1, первый COUNT: {first}")

        await s2.execute(text("BEGIN"))
        await s2.execute(
            text(
                "INSERT INTO products (name, price, in_stock) "
                "VALUES ('phantom-1', 1.00, TRUE)"
            )
        )
        await s2.execute(text("COMMIT"))
        print("Сессия 2: INSERT 'phantom-1' + COMMIT")

        result = await s1.execute(
            text("SELECT COUNT(*) FROM products WHERE name LIKE 'phantom-%'")
        )
        second = int(result.scalar_one())
        print(f"Сессия 1, второй COUNT: {second}")

        if first == second:
            print(f"  -> Фантомов НЕТ: {first} == {second}")
        else:
            print(f"  -> PHANTOM READ: {first} != {second}")

        await s1.execute(text("ROLLBACK"))

        await s2.execute(text("DELETE FROM products WHERE name LIKE 'phantom-%'"))
        await s2.commit()
    finally:
        await s1.close()
        await s2.close()


async def demo_no_phantom_read_serializable() -> None:
    print("\n" + "=" * 70)
    print("6. Нет phantom reads при SERIALIZABLE")
    print("=" * 70)
    print("То же самое, но уровень SERIALIZABLE — самый строгий.\n")

    async with async_session() as s:
        await s.execute(text("DELETE FROM products WHERE name LIKE 'phantom-%'"))
        await s.commit()

    s1 = async_session()
    s2 = async_session()
    try:
        await s1.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
        await s1.execute(text("BEGIN"))

        result = await s1.execute(
            text("SELECT COUNT(*) FROM products WHERE name LIKE 'phantom-%'")
        )
        first = int(result.scalar_one())
        print(f"Сессия 1, первый COUNT: {first}")

        await s2.execute(text("BEGIN"))
        await s2.execute(
            text(
                "INSERT INTO products (name, price, in_stock) "
                "VALUES ('phantom-2', 1.00, TRUE)"
            )
        )
        await s2.execute(text("COMMIT"))
        print("Сессия 2: INSERT 'phantom-2' + COMMIT")

        result = await s1.execute(
            text("SELECT COUNT(*) FROM products WHERE name LIKE 'phantom-%'")
        )
        second = int(result.scalar_one())
        print(f"Сессия 1, второй COUNT: {second}")

        if first == second:
            print(f"  -> Фантомов НЕТ: {first} == {second}")

        await s1.execute(text("ROLLBACK"))

        await s2.execute(text("DELETE FROM products WHERE name LIKE 'phantom-%'"))
        await s2.commit()
    finally:
        await s1.close()
        await s2.close()


async def main() -> None:
    await demo_dirty_read()
    await demo_no_dirty_read_read_committed()
    await demo_non_repeatable_read()
    await demo_no_non_repeatable_read()
    await demo_phantom_read()
    await demo_no_phantom_read_serializable()

    await engine.dispose()
    print("\nГотово.")


if __name__ == "__main__":
    asyncio.run(main())