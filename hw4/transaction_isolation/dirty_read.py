from sqlalchemy import text

from transaction_isolation.common import engine_for, prepare_value_table


def run_case(isolation_level: str) -> tuple[int, int]:
    prepare_value_table()
    writer_engine = engine_for("READ COMMITTED")
    reader_engine = engine_for(isolation_level)

    with writer_engine.connect() as writer, reader_engine.connect() as reader:
        writer_transaction = writer.begin()
        reader_transaction = reader.begin()

        writer.execute(text("UPDATE isolation_values SET value = 999 WHERE id = 1"))
        seen = reader.scalar(text("SELECT value FROM isolation_values WHERE id = 1"))

        writer_transaction.rollback()
        after_rollback = reader.scalar(
            text("SELECT value FROM isolation_values WHERE id = 1")
        )
        reader_transaction.commit()

    writer_engine.dispose()
    reader_engine.dispose()
    return int(seen), int(after_rollback)


def main() -> None:
    print("\nDIRTY READ")
    for level in ("READ UNCOMMITTED", "READ COMMITTED"):
        seen, after_rollback = run_case(level)
        print(f"{level}: до rollback={seen}, после rollback={after_rollback}")

    print(
        "PostgreSQL не допускает dirty read: READ UNCOMMITTED в нем работает "
        "как READ COMMITTED. Поэтому в обоих случаях читается 100, а не "
        "незакоммиченное значение 999."
    )


if __name__ == "__main__":
    main()
