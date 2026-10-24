
import os

from sqlalchemy import create_engine, text


engine = create_engine(os.environ["database_url".upper()])


# Отдельная таблица, чтобы не затрагивать Shop API.
with engine.begin() as connection:
    connection.execute(text("""
        create table if not exists phantom_demo (
            id integer primary key,
            price integer not null
        )
    """))


def demonstrate_phantom_read(isolation_level: str) -> None:
    # Подготавливаем одинаковое состояние для каждого теста.
    with engine.begin() as connection:
        connection.execute(text("delete from phantom_demo"))
        connection.execute(text("""
            insert into phantom_demo (id, price)
            values (1, 100)
        """))

    print(f"\nIsolation level: {isolation_level}")

    # Транзакция A: два чтения в одной транзакции.
    with engine.connect().execution_options(
            isolation_level=isolation_level
    ) as reader:
        with reader.begin():

            # Первое чтение.
            first_count = reader.execute(text("""
                select count(*)
                from phantom_demo
                where price >= 100
            """)).scalar_one()

            print(f"First read: {first_count} rows")

            # Транзакция B добавляет новую запись.
            with engine.begin() as writer:
                writer.execute(text("""
                    insert into phantom_demo (id, price)
                    values (2, 200)
                """))

            print("Writer inserted new row and committed")

            # Второе чтение в той же транзакции A.
            second_count = reader.execute(text("""
                select count(*)
                from phantom_demo
                where price >= 100
            """)).scalar_one()

            print(f"Second read: {second_count} rows")

            if first_count != second_count:
                print("Phantom read detected!")
            else:
                print("No phantom read!")


for level in (
        "read uncommitted",
        "read committed",
        "repeatable read",
        "serializable",
):
    demonstrate_phantom_read(level.upper())
