import threading

from sqlalchemy import text

from transactions.common import heading, make_engine, run_concurrently


def read_price_twice(isolation_level: str) -> list[int]:
    engine = make_engine()
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS tx_demo_items"))
        connection.execute(
            text(
                "CREATE TABLE tx_demo_items ("
                "id integer PRIMARY KEY, price integer NOT NULL)"
            )
        )
        connection.execute(
            text("INSERT INTO tx_demo_items (id, price) VALUES (1, 100)")
        )

    first_read_done = threading.Event()
    update_committed = threading.Event()
    prices: list[int] = []

    def reader() -> None:
        with engine.connect().execution_options(
            isolation_level=isolation_level
        ) as connection:
            with connection.begin():
                prices.append(
                    connection.scalar(
                        text("SELECT price FROM tx_demo_items WHERE id = 1")
                    )
                )
                first_read_done.set()
                if not update_committed.wait(timeout=10):
                    raise TimeoutError("Writer did not commit")
                prices.append(
                    connection.scalar(
                        text("SELECT price FROM tx_demo_items WHERE id = 1")
                    )
                )

    def writer() -> None:
        if not first_read_done.wait(timeout=10):
            raise TimeoutError("Reader did not perform its first SELECT")
        try:
            with engine.begin() as connection:
                connection.execute(
                    text("UPDATE tx_demo_items SET price = 200 WHERE id = 1")
                )
        finally:
            update_committed.set()

    run_concurrently(reader, writer)
    engine.dispose()
    return prices


def main() -> None:
    heading("Non-repeatable read: item price")
    read_committed = read_price_twice("READ COMMITTED")
    repeatable_read = read_price_twice("REPEATABLE READ")

    print(f"READ COMMITTED: {read_committed}")
    print(f"REPEATABLE READ: {repeatable_read}")
    assert read_committed == [100, 200]
    assert repeatable_read == [100, 100]
    print("PASS: REPEATABLE READ keeps the item price stable for both SELECTs.")


if __name__ == "__main__":
    main()
