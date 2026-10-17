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
        first_value = connection_b.execute(
            text("SELECT value FROM isolation_demo WHERE id = 1")
        ).scalar_one()
        print(f"B first read: {first_value}")
        with connection_a.begin():
            connection_a.execute(
                text(
                    """
                    UPDATE isolation_demo
                    SET value = 200
                    WHERE id = 1
                    """
                )
            )
        print("A changed value to 200 and committed")
        second_value = connection_b.execute(
            text("SELECT value FROM isolation_demo WHERE id = 1")
        ).scalar_one()
        print(f"B second read: {second_value}")
    finally:
        if transaction_b.is_active:
            transaction_b.rollback()
        connection_b.close()
        connection_a.close()


run_test("READ COMMITTED")
run_test("REPEATABLE READ")