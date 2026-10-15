from sqlalchemy import text

from transaction_isolation.common import engine_for, prepare_phantom_table


def run_case(isolation_level: str) -> tuple[int, int]:
    prepare_phantom_table()
    reader_engine = engine_for(isolation_level)
    writer_engine = engine_for("READ COMMITTED")

    with reader_engine.connect() as reader, writer_engine.connect() as writer:
        reader_transaction = reader.begin()
        first_count = reader.scalar(
            text("SELECT COUNT(*) FROM isolation_orders WHERE amount >= 100")
        )

        with writer.begin():
            writer.execute(text("INSERT INTO isolation_orders (amount) VALUES (300)"))

        second_count = reader.scalar(
            text("SELECT COUNT(*) FROM isolation_orders WHERE amount >= 100")
        )
        reader_transaction.commit()

    reader_engine.dispose()
    writer_engine.dispose()
    return int(first_count), int(second_count)


def main() -> None:
    print("\nPHANTOM READ")
    for level in ("READ COMMITTED", "REPEATABLE READ", "SERIALIZABLE"):
        first, second = run_case(level)
        print(f"{level}: строк при первом чтении={first}, при втором={second}")

    print(
        "В PostgreSQL фантом появляется уже при READ COMMITTED. Его "
        "REPEATABLE READ сильнее минимального требования SQL и не допускает "
        "фантомов; SERIALIZABLE также их не допускает."
    )


if __name__ == "__main__":
    main()
