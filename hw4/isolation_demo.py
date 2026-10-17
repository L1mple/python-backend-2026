
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError


# Получаем адрес базы данных из переменной окружения.
# Если переменная не задана, используем локальный PostgreSQL.
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://shop:shop@localhost:5433/shop"
)

# Создаём подключение к базе данных через SQLAlchemy.
engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def reset_data() -> None:
    """Подготавливает одинаковое исходное состояние БД перед каждым экспериментом."""
    with engine.begin() as conn:
        # Создаём таблицы для демонстрации различных проблем транзакций.
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS hw4_tx_value "
                "(id INT PRIMARY KEY, value INT NOT NULL)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS hw4_tx_phantoms "
                "(id INT PRIMARY KEY, category TEXT NOT NULL)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS hw4_tx_doctors "
                "(id INT PRIMARY KEY, on_call BOOLEAN NOT NULL)"
            )
        )

        # Очищаем таблицы от результатов предыдущих экспериментов.
        conn.execute(
            text(
                "TRUNCATE TABLE hw4_tx_value, "
                "hw4_tx_phantoms, hw4_tx_doctors"
            )
        )

        # Заполняем таблицы начальными данными.
        conn.execute(
            text("INSERT INTO hw4_tx_value (id, value) VALUES (1, 100)")
        )
        conn.execute(
            text(
                "INSERT INTO hw4_tx_phantoms (id, category) "
                "VALUES (1, 'shop')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO hw4_tx_doctors (id, on_call) "
                "VALUES (1, TRUE), (2, TRUE)"
            )
        )


def dirty_read(level: str) -> int:
    """Проверяет возможность грязного чтения на заданном уровне изоляции.

    Транзакция T1 изменяет значение, но не фиксирует изменения.
    Транзакция T2 пытается прочитать это значение до завершения T1.

    PostgreSQL не допускает грязное чтение даже на READ UNCOMMITTED.
    """
    reset_data()

    with (
        engine.connect() as writer,
        engine.connect().execution_options(isolation_level=level) as reader,
    ):
        # Начинаем транзакцию T1.
        writer_tx = writer.begin()

        try:
            # T1 изменяет значение со 100 на 999 без COMMIT.
            writer.execute(
                text("UPDATE hw4_tx_value SET value = 999 WHERE id = 1")
            )

            # T2 читает значение, пока изменения T1 ещё не зафиксированы.
            with reader.begin():
                observed = int(
                    reader.scalar(
                        text("SELECT value FROM hw4_tx_value WHERE id = 1")
                    )
                )
        finally:
            # Отменяем незавершённые изменения T1.
            writer_tx.rollback()

    return observed


def non_repeatable_read(level: str) -> tuple[int, int]:
    """Демонстрирует неповторяемое чтение.

    T1 дважды читает одну и ту же строку.
    Между чтениями T2 изменяет значение и фиксирует изменения.

    READ COMMITTED позволяет T1 увидеть новое значение.
    REPEATABLE READ сохраняет первоначальное значение для T1.
    """
    reset_data()

    with (
        engine.connect().execution_options(isolation_level=level) as t1,
        engine.connect() as t2,
    ):
        with t1.begin():
            # Первое чтение T1.
            before = int(
                t1.scalar(
                    text("SELECT value FROM hw4_tx_value WHERE id = 1")
                )
            )

            # T2 изменяет значение и выполняет COMMIT.
            with t2.begin():
                t2.execute(
                    text(
                        "UPDATE hw4_tx_value "
                        "SET value = 200 WHERE id = 1"
                    )
                )

            # Повторное чтение T1 в рамках той же транзакции.
            after = int(
                t1.scalar(
                    text("SELECT value FROM hw4_tx_value WHERE id = 1")
                )
            )

    return before, after


def phantom_read(level: str) -> tuple[int, int]:
    """Демонстрирует фантомное чтение.

    T1 дважды подсчитывает количество строк, соответствующих условию.
    Между запросами T2 добавляет новую строку и фиксирует изменения.

    При READ COMMITTED количество строк может измениться.
    PostgreSQL предотвращает фантомное чтение уже на REPEATABLE READ.
    """
    reset_data()

    with (
        engine.connect().execution_options(isolation_level=level) as t1,
        engine.connect() as t2,
    ):
        with t1.begin():
            # T1 подсчитывает количество товаров в категории shop.
            before = int(
                t1.scalar(
                    text(
                        "SELECT COUNT(*) FROM hw4_tx_phantoms "
                        "WHERE category = 'shop'"
                    )
                )
            )

            # T2 добавляет новую строку и фиксирует изменения.
            with t2.begin():
                t2.execute(
                    text(
                        "INSERT INTO hw4_tx_phantoms (id, category) "
                        "VALUES (2, 'shop')"
                    )
                )

            # T1 повторяет тот же запрос.
            after = int(
                t1.scalar(
                    text(
                        "SELECT COUNT(*) FROM hw4_tx_phantoms "
                        "WHERE category = 'shop'"
                    )
                )
            )

    return before, after


def write_skew(level: str) -> tuple[list[str], int]:
    """Демонстрирует аномалию write skew и работу SERIALIZABLE.

    В больнице дежурят два врача. По правилу хотя бы один
    врач должен оставаться на дежурстве.

    Оба врача одновременно проверяют количество дежурных
    и пытаются завершить свою смену.

    При REPEATABLE READ обе транзакции могут успешно завершиться,
    нарушив правило: на дежурстве не останется никого.

    При SERIALIZABLE PostgreSQL отменяет одну из конфликтующих
    транзакций с ошибкой SQLSTATE 40001.
    """
    reset_data()

    # Барьер обеспечивает одновременную работу двух транзакций.
    # Каждая транзакция дождётся другой после чтения данных.
    barrier = Barrier(2, timeout=15)

    def go_off_duty(doctor_id: int) -> str:
        """Пытается снять врача с дежурства в отдельной транзакции."""
        with engine.connect().execution_options(isolation_level=level) as conn:
            try:
                with conn.begin():
                    # Проверяем, сколько врачей сейчас дежурит.
                    on_call = int(
                        conn.scalar(
                            text(
                                "SELECT COUNT(*) FROM hw4_tx_doctors "
                                "WHERE on_call = TRUE"
                            )
                        )
                    )

                    # Ожидаем, пока обе транзакции выполнят чтение.
                    barrier.wait()

                    # Врач может уйти, если на дежурстве больше одного человека.
                    if on_call > 1:
                        conn.execute(
                            text(
                                "UPDATE hw4_tx_doctors "
                                "SET on_call = FALSE "
                                "WHERE id = :doctor_id"
                            ),
                            {"doctor_id": doctor_id},
                        )

                # Транзакция успешно зафиксирована.
                return f"врач {doctor_id}: COMMIT"

            except DBAPIError as exc:
                # PostgreSQL использует код 40001 для ошибок сериализации.
                if getattr(exc.orig, "sqlstate", None) == "40001":
                    return (
                        f"врач {doctor_id}: "
                        "ROLLBACK (ошибка сериализации 40001)"
                    )
                raise

    # Запускаем две транзакции параллельно в разных потоках.
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(go_off_duty, 1),
            pool.submit(go_off_duty, 2),
        ]
        results = [future.result() for future in futures]

    # Проверяем, сколько врачей осталось на дежурстве.
    with engine.connect() as conn:
        remaining = int(
            conn.scalar(
                text(
                    "SELECT COUNT(*) FROM hw4_tx_doctors "
                    "WHERE on_call = TRUE"
                )
            )
        )

    return results, remaining


def main() -> None:
    """Последовательно запускает эксперименты с уровнями изоляции транзакций."""

    # Проверяем, что используется PostgreSQL.
    if engine.dialect.name != "postgresql":
        raise SystemExit(
            "Для корректной демонстрации уровней изоляции требуется PostgreSQL"
        )

    # Эксперимент 1. Грязное чтение.
    print("\n1) DIRTY READ — грязное чтение")
    print(
        "   В PostgreSQL READ UNCOMMITTED "
        "фактически работает как READ COMMITTED."
    )

    for level in ("READ UNCOMMITTED", "READ COMMITTED"):
        result = dirty_read(level)

        print(
            f"   {level}: T1 записала 999 без COMMIT, "
            f"T2 увидела {result}"
        )

        # Незавершённые изменения не должны быть видны.
        assert result == 100

    # Эксперимент 2. Неповторяемое чтение.
    print("\n2) NON-REPEATABLE READ — неповторяемое чтение")

    for level, expected in (
        ("READ COMMITTED", (100, 200)),
        ("REPEATABLE READ", (100, 100)),
    ):
        observed = non_repeatable_read(level)

        print(
            f"   {level}: первое чтение {observed[0]}, "
            f"второе {observed[1]}"
        )

        # Проверяем ожидаемые результаты для каждого уровня.
        assert observed == expected

    # Эксперимент 3. Фантомное чтение.
    print("\n3) PHANTOM READ — фантомное чтение")
    print(
        "   В PostgreSQL фантомное чтение не возникает "
        "уже на уровне REPEATABLE READ."
    )

    for level, expected in (
        ("READ COMMITTED", (1, 2)),
        ("REPEATABLE READ", (1, 1)),
        ("SERIALIZABLE", (1, 1)),
    ):
        observed = phantom_read(level)

        print(
            f"   {level}: первое чтение {observed[0]}, "
            f"второе {observed[1]}"
        )

        assert observed == expected

    # Эксперимент 4. Аномалия write skew.
    print("\n4) WRITE SKEW — конфликт параллельных транзакций")
    print(
        "   Демонстрация преимуществ SERIALIZABLE "
        "по сравнению с REPEATABLE READ."
    )

    for level, expected in (
        ("REPEATABLE READ", 0),
        ("SERIALIZABLE", 1),
    ):
        results, remaining = write_skew(level)

        print(
            f"   {level}: {', '.join(results)}; "
            f"врачей на дежурстве: {remaining}"
        )

        # На SERIALIZABLE хотя бы один врач должен остаться.
        assert remaining == expected

    print(
        "\nВсе проверяемые для PostgreSQL "
        "сценарии завершились успешно."
    )


if __name__ == "__main__":
    main()
