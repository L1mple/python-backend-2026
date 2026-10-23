import threading

from sqlalchemy import text

from transactions.common import heading, make_engine, run_concurrently


def observe_uncommitted_price(isolation_level: str) -> tuple[str, int]:
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

    update_done = threading.Event()
    read_done = threading.Event()
    result: dict[str, str | int] = {}

    def writer() -> None:
        with engine.connect() as connection:
            transaction = connection.begin()
            connection.execute(
                text("UPDATE tx_demo_items SET price = 999 WHERE id = 1")
            )
            update_done.set()
            if not read_done.wait(timeout=10):
                raise TimeoutError("Reader did not inspect the uncommitted price")
            transaction.rollback()

    def reader() -> None:
        if not update_done.wait(timeout=10):
            raise TimeoutError("Writer did not update the item")
        try:
            with engine.connect().execution_options(
                isolation_level=isolation_level
            ) as connection:
                with connection.begin():
                    result["actual_level"] = connection.scalar(
                        text("SHOW transaction_isolation")
                    )
                    result["price"] = connection.scalar(
                        text("SELECT price FROM tx_demo_items WHERE id = 1")
                    )
        finally:
            read_done.set()

    run_concurrently(writer, reader)
    engine.dispose()
    return str(result["actual_level"]), int(result["price"])


def main() -> None:
    heading("Dirty read: item price")
    for isolation_level in ("READ UNCOMMITTED", "READ COMMITTED"):
        actual_level, price = observe_uncommitted_price(isolation_level)
        print(
            f"{isolation_level}: PostgreSQL reports {actual_level!r}; "
            f"reader saw price {price}, uncommitted price was 999"
        )
        assert price == 100

    print(
        "PASS: PostgreSQL treats READ UNCOMMITTED like READ COMMITTED, "
        "so dirty reads cannot be reproduced."
    )


if __name__ == "__main__":
    main()
