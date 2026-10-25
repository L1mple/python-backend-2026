import os

from sqlalchemy import create_engine, text


database_url = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://shop:shop@localhost:5432/shop",
)


def prepare_table() -> None:
    engine = create_engine(database_url)

    with engine.begin() as connection:
        connection.execute(
            text("""
                drop table if exists transaction_test
            """)
        )

        connection.execute(
            text("""
                create table transaction_test (
                    id integer primary key,
                    value integer not null
                )
            """)
        )

        connection.execute(
            text("""
                insert into transaction_test (id, value)
                values (1, 100)
            """)
        )


def dirty_read() -> None:
    print("\n=== dirty read, read uncommitted ===")

    engine = create_engine(
        database_url,
        isolation_level="READ UNCOMMITTED",
    )

    connection1 = engine.connect()
    connection2 = engine.connect()

    transaction1 = connection1.begin()
    transaction2 = connection2.begin()

    try:
        initial_value = connection2.execute(
            text("select value from transaction_test where id = 1")
        ).scalar_one()

        print("initial value:", initial_value)

        connection1.execute(
            text("""
                update transaction_test
                set value = 200
                where id = 1
            """)
        )

        print("transaction 1 changed value to 200, but did not commit")

        value = connection2.execute(
            text("select value from transaction_test where id = 1")
        ).scalar_one()

        print("transaction 2 sees:", value)
        print("postgresql does not allow dirty reads even at read uncommitted")

    finally:
        transaction1.rollback()
        transaction2.rollback()

        connection1.close()
        connection2.close()


def non_repeatable_read() -> None:
    print("\n=== non-repeatable read, read committed ===")

    engine = create_engine(
        database_url,
        isolation_level="READ COMMITTED",
    )

    connection1 = engine.connect()
    connection2 = engine.connect()

    transaction1 = connection1.begin()
    transaction2 = connection2.begin()

    try:
        first_value = connection1.execute(
            text("select value from transaction_test where id = 1")
        ).scalar_one()

        print("transaction 1 first read:", first_value)

        connection2.execute(
            text("""
                update transaction_test
                set value = 300
                where id = 1
            """)
        )

        transaction2.commit()

        second_value = connection1.execute(
            text("select value from transaction_test where id = 1")
        ).scalar_one()

        print("transaction 1 second read:", second_value)

    finally:
        transaction1.rollback()

        connection1.close()
        connection2.close()


def repeatable_read() -> None:
    print("\n=== repeatable read ===")

    engine = create_engine(
        database_url,
        isolation_level="REPEATABLE READ",
    )

    connection1 = engine.connect()
    connection2 = engine.connect()

    transaction1 = connection1.begin()
    transaction2 = connection2.begin()

    try:
        first_value = connection1.execute(
            text("select value from transaction_test where id = 1")
        ).scalar_one()

        print("transaction 1 first read:", first_value)

        connection2.execute(
            text("""
                update transaction_test
                set value = 300
                where id = 1
            """)
        )

        transaction2.commit()

        second_value = connection1.execute(
            text("select value from transaction_test where id = 1")
        ).scalar_one()

        print("transaction 1 second read:", second_value)
        print("non-repeatable read does not occur")

    finally:
        transaction1.rollback()

        connection1.close()
        connection2.close()


def phantom_read() -> None:
    print("\n=== phantom read, repeatable read ===")

    engine = create_engine(
        database_url,
        isolation_level="REPEATABLE READ",
    )

    connection1 = engine.connect()
    connection2 = engine.connect()

    transaction1 = connection1.begin()
    transaction2 = connection2.begin()

    try:
        first_count = connection1.execute(
            text("select count(*) from transaction_test")
        ).scalar_one()

        print("transaction 1 first count:", first_count)

        connection2.execute(
            text("""
                insert into transaction_test (id, value)
                values (2, 200)
            """)
        )

        transaction2.commit()

        second_count = connection1.execute(
            text("select count(*) from transaction_test")
        ).scalar_one()

        print("transaction 1 second count:", second_count)
        print("postgresql does not allow phantom reads at repeatable read")

    finally:
        transaction1.rollback()

        connection1.close()
        connection2.close()


def serializable_read() -> None:
    print("\n=== serializable ===")

    engine = create_engine(
        database_url,
        isolation_level="SERIALIZABLE",
    )

    connection1 = engine.connect()
    connection2 = engine.connect()

    transaction1 = connection1.begin()
    transaction2 = connection2.begin()

    try:
        first_count = connection1.execute(
            text("select count(*) from transaction_test")
        ).scalar_one()

        print("transaction 1 first count:", first_count)

        connection2.execute(
            text("""
                insert into transaction_test (id, value)
                values (2, 200)
            """)
        )

        transaction2.commit()

        second_count = connection1.execute(
            text("select count(*) from transaction_test")
        ).scalar_one()

        print("transaction 1 second count:", second_count)
        print("phantom read does not occur")

    finally:
        transaction1.rollback()

        connection1.close()
        connection2.close()


if __name__ == "__main__":
    prepare_table()
    dirty_read()

    prepare_table()
    non_repeatable_read()

    prepare_table()
    repeatable_read()

    prepare_table()
    phantom_read()

    prepare_table()
    serializable_read()