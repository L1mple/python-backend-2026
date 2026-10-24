
import os

from sqlalchemy import create_engine, text


engine = create_engine(os.environ["DATABASE_URL"])


with engine.begin() as connection:
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS non_repeatable_demo (
            id INTEGER PRIMARY KEY,
            value INTEGER NOT NULL
        )
    """))


def demonstrate_non_repeatable_read(isolation_level: str):
    # Возвращаем исходное значение перед каждым тестом.
    with engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO non_repeatable_demo (id, value)
            VALUES (1, 100)
            ON CONFLICT (id)
            DO UPDATE SET value = 100
        """))

    print(f"\nIsolation level: {isolation_level}")

    # Транзакция A
    with engine.connect().execution_options(
            isolation_level=isolation_level
    ) as reader:

        first_value = reader.execute(text("""
            SELECT value FROM non_repeatable_demo WHERE id = 1
        """)).scalar_one()

        print(f"First read: {first_value}")

        # Транзакция B меняет значение и фиксирует его.
        with engine.begin() as writer:
            writer.execute(text("""
                UPDATE non_repeatable_demo
                SET value = 200
                WHERE id = 1
            """))

        print("Writer committed value: 200")

        # Транзакция A читает снова, не завершая свою транзакцию.
        second_value = reader.execute(text("""
            SELECT value FROM non_repeatable_demo WHERE id = 1
        """)).scalar_one()

        print(f"Second read: {second_value}")

        if first_value != second_value:
            print("Non-repeatable read detected!")
        else:
            print("Repeatable read preserved!")

        reader.rollback()


for level in [
    "READ UNCOMMITTED",
    "READ COMMITTED",
    "REPEATABLE READ",
    "SERIALIZABLE",
]:
    demonstrate_non_repeatable_read(level)
