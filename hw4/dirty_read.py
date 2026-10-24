
import os

from sqlalchemy import create_engine, text


engine = create_engine(os.environ["DATABASE_URL"])


# Подготовка отдельной таблицы для эксперимента
with engine.begin() as connection:
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS isolation_demo (
            id INTEGER PRIMARY KEY,
            value INTEGER NOT NULL
        )
    """))


def demonstrate_dirty_read(isolation_level: str) -> None:
    # Каждый эксперимент начинается с одинакового значения.
    with engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO isolation_demo (id, value)
            VALUES (1, 100)
            ON CONFLICT (id)
            DO UPDATE SET value = 100
        """))

    print(f"\nIsolation level: {isolation_level}")

    # Два независимых подключения = две транзакции.
    with engine.connect() as writer:
        with engine.connect().execution_options(
                isolation_level=isolation_level
        ) as reader:

            writer_transaction = writer.begin()
            reader_transaction = reader.begin()

            # Первая транзакция меняет значение, но НЕ сохраняет.
            writer.execute(text("""
                UPDATE isolation_demo
                SET value = 200
                WHERE id = 1
            """))

            # Вторая транзакция пытается увидеть изменение.
            value = reader.execute(text("""
                SELECT value
                FROM isolation_demo
                WHERE id = 1
            """)).scalar_one()

            print(f"Uncommitted value: 200")
            print(f"Reader sees: {value}")

            # Отменяем изменение первой транзакции.
            writer_transaction.rollback()
            reader_transaction.rollback()


demonstrate_dirty_read("READ UNCOMMITTED")
demonstrate_dirty_read("READ COMMITTED")
