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
    transaction_a = connection_a.begin()
    transaction_b = connection_b.begin()
    try:
        print(f"\nIsolation: {isolation_level}")
        initial_value = connection_b.execute(
            text("SELECT value FROM isolation_demo WHERE id = 1")
        ).scalar_one()
        print(f"B reads initial value: {initial_value}")
        connection_a.execute(
            text(
                """
                UPDATE isolation_demo
                SET value = 200
                WHERE id = 1
                """
            )
        )
        value_in_a = connection_a.execute(
            text("SELECT value FROM isolation_demo WHERE id = 1")
        ).scalar_one()
        print(f"A changed value but did not commit: {value_in_a}")
        value_in_b = connection_b.execute(
            text("SELECT value FROM isolation_demo WHERE id = 1")
        ).scalar_one()
        print(f"B reads while A has not committed: {value_in_b}")
    finally:
        transaction_b.rollback()
        transaction_a.rollback()
        connection_b.close()
        connection_a.close()

run_test("READ UNCOMMITTED")
run_test("READ COMMITTED")