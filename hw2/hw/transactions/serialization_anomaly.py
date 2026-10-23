import threading

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from transactions.common import heading, make_engine, run_concurrently


def run_inventory_write_skew(isolation_level: str) -> tuple[dict[int, str], int]:
    engine = make_engine()
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS tx_demo_inventory"))
        connection.execute(
            text(
                "CREATE TABLE tx_demo_inventory ("
                "copy_id integer PRIMARY KEY, in_stock boolean NOT NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO tx_demo_inventory (copy_id, in_stock) "
                "VALUES (1, true), (2, true)"
            )
        )

    both_have_read = threading.Barrier(2)
    outcomes: dict[int, str] = {}

    def remove_copy_from_stock(copy_id: int) -> None:
        with engine.connect().execution_options(
            isolation_level=isolation_level
        ) as connection:
            transaction = connection.begin()
            try:
                copies_in_stock = connection.scalar(
                    text("SELECT count(*) FROM tx_demo_inventory WHERE in_stock")
                )
                both_have_read.wait(timeout=10)
                if copies_in_stock > 1:
                    connection.execute(
                        text(
                            "UPDATE tx_demo_inventory SET in_stock = false "
                            "WHERE copy_id = :copy_id"
                        ),
                        {"copy_id": copy_id},
                    )
                transaction.commit()
                outcomes[copy_id] = "committed"
            except DBAPIError as error:
                if transaction.is_active:
                    transaction.rollback()
                sqlstate = getattr(error.orig, "sqlstate", "unknown")
                outcomes[copy_id] = f"aborted ({sqlstate})"

    run_concurrently(
        lambda: remove_copy_from_stock(1),
        lambda: remove_copy_from_stock(2),
    )
    with engine.connect() as connection:
        remaining = connection.scalar(
            text("SELECT count(*) FROM tx_demo_inventory WHERE in_stock")
        )
    engine.dispose()
    return outcomes, remaining


def main() -> None:
    heading("Serialization anomaly: invetory write skew")
    repeatable_outcomes, repeatable_remaining = run_inventory_write_skew(
        "REPEATABLE READ"
    )
    serializable_outcomes, serializable_remaining = run_inventory_write_skew(
        "SERIALIZABLE"
    )

    print(
        f"REPEATABLE READ: {repeatable_outcomes}; "
        f"copies left in stock: {repeatable_remaining}"
    )
    print(
        f"SERIALIZABLE: {serializable_outcomes}; "
        f"copies left in stock: {serializable_remaining}"
    )
    assert list(repeatable_outcomes.values()).count("committed") == 2
    assert repeatable_remaining == 0
    assert list(serializable_outcomes.values()).count("committed") == 1
    assert serializable_remaining == 1
    assert any("40001" in outcome for outcome in serializable_outcomes.values())
    print(
        "PASS: SERIALIZABLE abroted one inventory transaction with SQLSTATE "
        "40001 and preserved the invariant that one copy remains in stock."
    )


if __name__ == "__main__":
    main()
