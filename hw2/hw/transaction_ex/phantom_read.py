from sqlalchemy import text
from shop_api.database import engine

def prepare_data() -> None:
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS isolation_demo"))
        connection.execute(
            text(
                """
                CREATE TABLE isolation_demo (
                    id INTEGER PRIMARY KEY,
                    value INTEGER NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO isolation_demo (id, value)
                VALUES (1, 100)
                """
            )
        )


def run_test(isolation_level: str) -> None:
    prepare_data()
    connection_a = engine.connect().execution_options(
        isolation_level=isolation_level,
    )
    connection_b = engine.connect().execution_options(
        isolation_level=isolation_level,
    )
    transaction_b = connection_b.begin()
    try:
        print(f"\nIsolation: {isolation_level}")
        first_count = connection_b.execute(
            text(
                """
                SELECT COUNT(*)
                FROM isolation_demo
                WHERE value >= 100
                """
            )
        ).scalar_one()
        print(f"B first read: {first_count} rows")
        with connection_a.begin():
            connection_a.execute(
                text(
                    """
                    INSERT INTO isolation_demo (id, value)
                    VALUES (2, 200)
                    """
                )
            )
        print("A inserted a new row and committed")
        second_count = connection_b.execute(
            text(
                """
                SELECT COUNT(*)
                FROM isolation_demo
                WHERE value >= 100
                """
            )
        ).scalar_one()
        print(f"B second read: {second_count} rows")
    finally:
        if transaction_b.is_active:
            transaction_b.rollback()
        connection_b.close()
        connection_a.close()

run_test("READ COMMITTED")
run_test("REPEATABLE READ")
run_test("SERIALIZABLE")