from sqlalchemy import text

from transaction_isolation.common import engine_for, prepare_value_table


def run_case(isolation_level: str) -> tuple[int, int]:
    prepare_value_table()
    reader_engine = engine_for(isolation_level)
    writer_engine = engine_for("READ COMMITTED")

    with reader_engine.connect() as reader, writer_engine.connect() as writer:
        reader_transaction = reader.begin()
        first_read = reader.scalar(
            text("SELECT value FROM isolation_values WHERE id = 1")
        )

        with writer.begin():
            writer.execute(text("UPDATE isolation_values SET value = 200 WHERE id = 1"))

        second_read = reader.scalar(
            text("SELECT value FROM isolation_values WHERE id = 1")
        )
        reader_transaction.commit()

    reader_engine.dispose()
    writer_engine.dispose()
    return int(first_read), int(second_read)


def main() -> None:
    print("\nNON-REPEATABLE READ")
    for level in ("READ COMMITTED", "REPEATABLE READ"):
        first, second = run_case(level)
        print(f"{level}: первое чтение={first}, второе чтение={second}")

    print(
        "При READ COMMITTED значение меняется между чтениями, а при "
        "REPEATABLE READ транзакция продолжает видеть свой первый снимок."
    )


if __name__ == "__main__":
    main()
