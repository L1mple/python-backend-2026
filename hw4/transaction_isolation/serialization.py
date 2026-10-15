from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from transaction_isolation.common import engine_for, prepare_doctors_table


def run_case(isolation_level: str) -> tuple[int, list[str]]:
    prepare_doctors_table()
    engine = engine_for(isolation_level)
    barrier = Barrier(2)

    def leave_shift(doctor_id: int) -> str:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                doctors_on_call = connection.scalar(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM isolation_doctors
                        WHERE on_call IS TRUE
                        """
                    )
                )
                barrier.wait(timeout=10)

                if doctors_on_call > 1:
                    connection.execute(
                        text(
                            """
                            UPDATE isolation_doctors
                            SET on_call = FALSE
                            WHERE id = :doctor_id
                            """
                        ),
                        {"doctor_id": doctor_id},
                    )

                transaction.commit()
                return f"doctor {doctor_id}: commit"
            except DBAPIError as error:
                transaction.rollback()
                if getattr(error.orig, "sqlstate", None) == "40001":
                    return f"doctor {doctor_id}: serialization failure 40001"
                raise

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(leave_shift, (1, 2)))

    with engine.connect() as connection:
        remaining = connection.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM isolation_doctors
                WHERE on_call IS TRUE
                """
            )
        )

    engine.dispose()
    return int(remaining), sorted(results)


def main() -> None:
    print("\nWRITE SKEW / SERIALIZATION")
    for level in ("REPEATABLE READ", "SERIALIZABLE"):
        remaining, results = run_case(level)
        print(f"{level}: дежурных осталось={remaining}; {'; '.join(results)}")

    print(
        "При REPEATABLE READ обе транзакции меняют разные строки и могут "
        "нарушить общее правило, оставив ноль дежурных. При SERIALIZABLE "
        "PostgreSQL отклоняет одну транзакцию с SQLSTATE 40001."
    )


if __name__ == "__main__":
    main()
