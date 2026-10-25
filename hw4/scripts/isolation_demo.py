#!/usr/bin/env python3
"""Демонстрация аномалий транзакций и уровней изоляции на PostgreSQL + SQLAlchemy.

Скрипт прогоняет 6 сценариев из задания:

    1. dirty read при READ UNCOMMITTED          -> в PostgreSQL НЕ воспроизводится
    2. dirty read при READ COMMITTED            -> отсутствует
    3. non-repeatable read при READ COMMITTED   -> ВОСПРОИЗВОДИТСЯ
    4. non-repeatable read при REPEATABLE READ  -> отсутствует
    5. phantom read при REPEATABLE READ         -> в PostgreSQL НЕ воспроизводится
    6. phantom read / аномалии при SERIALIZABLE -> отсутствует

Важные особенности PostgreSQL, которые демонстрирует скрипт:

* READ UNCOMMITTED в PostgreSQL фактически эквивалентен READ COMMITTED:
  движок никогда не читает незакоммиченные данные, поэтому dirty read
  показать невозможно ни на каком уровне изоляции.
* REPEATABLE READ в PostgreSQL реализован как snapshot isolation:
  каждый транзакционный снапшот фиксируется на старте транзакции,
  поэтому phantom read на этом уровне тоже невозможен.
* «Дыра», которую закрывает SERIALIZABLE в PostgreSQL — аномалия
  write skew (сценарий 5b). При SERIALIZABLE вторая транзакция
  падает с ошибкой serialization_failure (SQLSTATE 40001).

Запуск (БД должна быть поднята, например `docker compose up -d db`):

    python scripts/isolation_demo.py [--db-url postgresql+psycopg2://ADMIN:123@127.0.0.1:5432/DB]
"""

from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

DEFAULT_DB_URL = "postgresql+psycopg2://ADMIN:123@127.0.0.1:5432/DB"

# ---------------------------------------------------------------------------
# Вспомогательные утилиты
# ---------------------------------------------------------------------------

_passed: list[str] = []
_failed: list[str] = []


def report(scenario: str, condition: bool, details: str) -> None:
    """Печатает результат сценария и запоминает его для итоговой сводки."""
    verdict = "OK " if condition else "FAIL"
    print(f"    [{verdict}] {details}")
    ( _passed if condition else _failed).append(scenario)


def begin_tx(engine: Engine, isolation: str):
    """Открывает соединение и начинает транзакцию с заданным уровнем изоляции."""
    conn = engine.connect()
    conn.begin()
    # SET TRANSACTION должен быть первым statement в транзакции.
    conn.exec_driver_sql(f"SET TRANSACTION ISOLATION LEVEL {isolation}")
    return conn


def reset(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS demo_items"))
        conn.execute(text("DROP TABLE IF EXISTS demo_doctors"))
        conn.execute(text("""
            CREATE TABLE demo_items (
                id    int PRIMARY KEY,
                price numeric NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE demo_doctors (
                id      int PRIMARY KEY,
                on_call boolean NOT NULL
            )
        """))


# ---------------------------------------------------------------------------
# Сценарии
# ---------------------------------------------------------------------------

def scenario_1_dirty_read_read_uncommitted(engine: Engine) -> None:
    """1. Dirty read при READ UNCOMMITTED.

    Ожидание по заданию: читаем незакоммиченное изменение.
    Фактически в PostgreSQL READ UNCOMMITTED = READ COMMITTED,
    поэтому аномалия НЕ воспроизводится — и это защита, а не баг скрипта.
    """
    print("\n[1] Dirty read при READ UNCOMMITTED")
    print("    T1: BEGIN ISOLATION LEVEL READ UNCOMMITTED; UPDATE demo_items SET price=999 (без COMMIT)")
    print("    T2: BEGIN ISOLATION LEVEL READ UNCOMMITTED; SELECT price -> видит 999?")

    with engine.begin() as conn:
        conn.execute(text("INSERT INTO demo_items (id, price) VALUES (1, 100)"))

    t1 = begin_tx(engine, "READ UNCOMMITTED")
    t1.execute(text("UPDATE demo_items SET price = 999 WHERE id = 1"))

    t2 = begin_tx(engine, "READ UNCOMMITTED")
    price = t2.execute(text("SELECT price FROM demo_items WHERE id = 1")).scalar_one()

    print(f"    T2 прочитал price = {price}")
    report(
        "1: dirty read @ read uncommitted",
        price == 100,
        "аномалия НЕ воспроизведена: PostgreSQL трактует READ UNCOMMITTED "
        "как READ COMMITTED и не отдаёт незакоммиченные данные (защита)",
    )

    t2.rollback()
    t1.rollback()


def scenario_2_no_dirty_read_read_committed(engine: Engine) -> None:
    """2. Нет dirty read при READ COMMITTED."""
    print("\n[2] Dirty read при READ COMMITTED (не должен возникать)")
    print("    T1: BEGIN; UPDATE demo_items SET price=999 (без COMMIT)")
    print("    T2: BEGIN ISOLATION LEVEL READ COMMITTED; SELECT price -> должен видеть 100")

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM demo_items"))
        conn.execute(text("INSERT INTO demo_items (id, price) VALUES (1, 100)"))

    t1 = begin_tx(engine, "READ COMMITTED")
    t1.execute(text("UPDATE demo_items SET price = 999 WHERE id = 1"))

    t2 = begin_tx(engine, "READ COMMITTED")
    price = t2.execute(text("SELECT price FROM demo_items WHERE id = 1")).scalar_one()

    print(f"    T2 прочитал price = {price}")
    report(
        "2: нет dirty read @ read committed",
        price == 100,
        "dirty read отсутствует: T2 видит только закоммиченное значение 100, а не 999",
    )

    t2.rollback()
    t1.rollback()


def scenario_3_non_repeatable_read_read_committed(engine: Engine) -> None:
    """3. Non-repeatable read при READ COMMITTED — воспроизводится."""
    print("\n[3] Non-repeatable read при READ COMMITTED")
    print("    T2: BEGIN; SELECT price (=100)")
    print("    T1: BEGIN; UPDATE price=200; COMMIT")
    print("    T2: SELECT price ещё раз -> 200?")

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM demo_items"))
        conn.execute(text("INSERT INTO demo_items (id, price) VALUES (1, 100)"))

    t2 = begin_tx(engine, "READ COMMITTED")
    first = t2.execute(text("SELECT price FROM demo_items WHERE id = 1")).scalar_one()
    print(f"    T2 первое чтение price = {first}")

    t1 = begin_tx(engine, "READ COMMITTED")
    t1.execute(text("UPDATE demo_items SET price = 200 WHERE id = 1"))
    t1.commit()
    print("    T1 закоммитил price = 200")

    second = t2.execute(text("SELECT price FROM demo_items WHERE id = 1")).scalar_one()
    print(f"    T2 второе чтение price = {second}")

    report(
        "3: non-repeatable read @ read committed",
        first == 100 and second == 200,
        "аномалия ВОСПРОИЗВЕДЕНА: одно и то же чтение внутри T2 дало разные "
        "значения (100 -> 200), потому что READ COMMITTED берёт свежий снапшот "
        "на каждый statement",
    )

    t2.rollback()


def scenario_4_no_non_repeatable_read_repeatable_read(engine: Engine) -> None:
    """4. Нет non-repeatable read при REPEATABLE READ."""
    print("\n[4] Non-repeatable read при REPEATABLE READ (не должен возникать)")
    print("    T2: BEGIN ISOLATION LEVEL REPEATABLE READ; SELECT price (=100)")
    print("    T1: UPDATE price=200; COMMIT")
    print("    T2: SELECT price -> всё ещё 100?")

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM demo_items"))
        conn.execute(text("INSERT INTO demo_items (id, price) VALUES (1, 100)"))

    t2 = begin_tx(engine, "REPEATABLE READ")
    first = t2.execute(text("SELECT price FROM demo_items WHERE id = 1")).scalar_one()
    print(f"    T2 первое чтение price = {first}")

    t1 = begin_tx(engine, "READ COMMITTED")
    t1.execute(text("UPDATE demo_items SET price = 200 WHERE id = 1"))
    t1.commit()
    print("    T1 закоммитил price = 200")

    second = t2.execute(text("SELECT price FROM demo_items WHERE id = 1")).scalar_one()
    print(f"    T2 второе чтение price = {second}")

    report(
        "4: нет non-repeatable read @ repeatable read",
        first == 100 and second == 100,
        "аномалия отсутствует: у REPEATABLE READ снапшот фиксируется на старте "
        "транзакции, оба чтения вернули 100",
    )

    t2.rollback()


def scenario_5_phantom_read_repeatable_read(engine: Engine) -> None:
    """5. Phantom read при REPEATABLE READ.

    В PostgreSQL этот сценарий НЕ воспроизводится: REPEATABLE READ = snapshot
    isolation, новые строки из чужих закоммиченных транзакций в снапшот не
    попадают. Скрипт честно показывает, что фантомов нет, а «дыру»,
    которую закрывает SERIALIZABLE, демонстрирует сценарий 5b (write skew).
    """
    print("\n[5] Phantom read при REPEATABLE READ")
    print("    T2: BEGIN ISOLATION LEVEL REPEATABLE READ; SELECT count(*) (=1)")
    print("    T1: INSERT новую строку; COMMIT")
    print("    T2: SELECT count(*) -> 2 (фантом)?")

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM demo_items"))
        conn.execute(text("INSERT INTO demo_items (id, price) VALUES (1, 100)"))

    t2 = begin_tx(engine, "REPEATABLE READ")
    first = t2.execute(text("SELECT count(*) FROM demo_items")).scalar_one()
    print(f"    T2 первое чтение count = {first}")

    t1 = begin_tx(engine, "READ COMMITTED")
    t1.execute(text("INSERT INTO demo_items (id, price) VALUES (2, 200)"))
    t1.commit()
    print("    T1 вставил строку id=2 и закоммитил")

    second = t2.execute(text("SELECT count(*) FROM demo_items")).scalar_one()
    print(f"    T2 второе чтение count = {second}")

    report(
        "5: phantom read @ repeatable read",
        first == 1 and second == 1,
        "фантом НЕ воспроизведён: в PostgreSQL REPEATABLE READ работает как "
        "snapshot isolation — снапшот транзакции не видит новых строк, "
        "вставленных после её старта (в отличие от стандарта SQL, где на "
        "этом уровне фантомы разрешены)",
    )

    t2.rollback()
    scenario_5b_write_skew(engine)


def scenario_5b_write_skew(engine: Engine) -> None:
    """5b. Write skew при REPEATABLE READ и его устранение на SERIALIZABLE.

    Инвариант: в клинике должен оставаться хотя бы один дежурный врач.
    T1 и T2 одновременно читают (2 дежурных), после чего каждый снимает
    с дежурства своего врача. При REPEATABLE READ обе транзакции опираются
    на устаревший снапшот и обе коммитятся — инвариант нарушен.
    При SERIALIZABLE вторая транзакция получает serialization_failure (40001)
    и откатывается — инвариант сохраняется.
    """
    print("\n[5b] Write skew: REPEATABLE READ vs SERIALIZABLE")
    print("    Инвариант: on_call_count >= 1. Обе T читают count=2, затем")
    print("    каждая выставляет своего врача on_call=false.")

    def seed() -> None:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM demo_doctors"))
            conn.execute(
                text("INSERT INTO demo_doctors (id, on_call) VALUES "
                     "(1, true), (2, true)")
            )

    def run(isolation: str) -> bool:
        """Возвращает True, если инвариант сохранился (>=1 дежурный)."""
        seed()
        t1 = begin_tx(engine, isolation)
        t2 = begin_tx(engine, isolation)
        t1.execute(text("SELECT count(*) FROM demo_doctors WHERE on_call"))
        t2.execute(text("SELECT count(*) FROM demo_doctors WHERE on_call"))
        t1.execute(text("UPDATE demo_doctors SET on_call = false WHERE id = 1"))
        t2.execute(text("UPDATE demo_doctors SET on_call = false WHERE id = 2"))
        t1.commit()
        try:
            t2.commit()
        except Exception as exc:  # noqa: BLE001 — ловим 40001 serialization_failure
            t2.rollback()
            print(f"    [{isolation}] T2 получила ошибку и откатилась: "
                  f"{type(exc.orig).__name__ if getattr(exc, 'orig', None) else type(exc).__name__}")
            return True
        with engine.begin() as conn:
            count = conn.execute(
                text("SELECT count(*) FROM demo_doctors WHERE on_call")
            ).scalar_one()
        print(f"    [{isolation}] обе транзакции закоммичены, on_call_count = {count}")
        return count >= 1

    invariant_ok_rr = run("REPEATABLE READ")
    report(
        "5b: write skew @ repeatable read",
        not invariant_ok_rr,
        "аномалия ВОСПРОИЗВЕДЕНА: обе транзакции читали устаревший снапшот, "
        "обе закоммитились, дежурных не осталось — REPEATABLE READ в "
        "PostgreSQL не защищает от write skew",
    )

    invariant_ok_ser = run("SERIALIZABLE")
    report(
        "5b: write skew @ serializable",
        invariant_ok_ser,
        "аномалия предотвращена: SERIALIZABLE вернул serialization_failure "
        "(SQLSTATE 40001) второй транзакции, инвариант сохранён",
    )


def scenario_6_no_anomalies_serializable(engine: Engine) -> None:
    """6. SERIALIZABLE: повтор сценария non-repeatable read + phantom.

    На уровне SERIALIZABLE повторные чтения стабильны, новые строки не
    появляются, а конкурирующие модификации откатываются с 40001.
    """
    print("\n[6] Аномалии при SERIALIZABLE (не должны возникать)")
    print("    T2: BEGIN ISOLATION LEVEL SERIALIZABLE; SELECT price (=100) и count (=1)")
    print("    T1: UPDATE price=200 + INSERT строку; COMMIT")
    print("    T2: повторные чтения -> price 100, count 1?")

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM demo_items"))
        conn.execute(text("INSERT INTO demo_items (id, price) VALUES (1, 100)"))

    t2 = begin_tx(engine, "SERIALIZABLE")
    first_price = t2.execute(
        text("SELECT price FROM demo_items WHERE id = 1")
    ).scalar_one()
    first_count = t2.execute(text("SELECT count(*) FROM demo_items")).scalar_one()
    print(f"    T2 первые чтения: price = {first_price}, count = {first_count}")

    t1 = begin_tx(engine, "READ COMMITTED")
    t1.execute(text("UPDATE demo_items SET price = 200 WHERE id = 1"))
    t1.execute(text("INSERT INTO demo_items (id, price) VALUES (2, 300)"))
    t1.commit()
    print("    T1 закоммитила UPDATE + INSERT")

    second_price = t2.execute(
        text("SELECT price FROM demo_items WHERE id = 1")
    ).scalar_one()
    second_count = t2.execute(text("SELECT count(*) FROM demo_items")).scalar_one()
    print(f"    T2 повторные чтения: price = {second_price}, count = {second_count}")

    report(
        "6: нет аномалий @ serializable",
        first_price == second_price == 100 and first_count == second_count == 1,
        "ни non-repeatable read, ни phantom: SERIALIZABLE даёт полную "
        "изолированность — снапшот стабилен, а конфликтующие модификации "
        "привели бы к откату с 40001 (см. сценарий 5b)",
    )

    t2.rollback()


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-url",
        default=os.getenv("DATABASE_URL", DEFAULT_DB_URL),
        help="SQLAlchemy URL подключения к PostgreSQL",
    )
    args = parser.parse_args()

    engine = create_engine(args.db_url)
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version()")).scalar_one()
    print(f"Подключено к: {args.db_url}")
    print(f"Сервер: {version}")

    reset(engine)

    scenario_1_dirty_read_read_uncommitted(engine)
    scenario_2_no_dirty_read_read_committed(engine)
    scenario_3_non_repeatable_read_read_committed(engine)
    scenario_4_no_non_repeatable_read_repeatable_read(engine)
    scenario_5_phantom_read_repeatable_read(engine)
    scenario_6_no_anomalies_serializable(engine)

    print("\n" + "=" * 70)
    print(f"ИТОГО: пройдено проверок — {len(_passed)}, провалено — {len(_failed)}")
    for name in _passed:
        print(f"  PASS {name}")
    for name in _failed:
        print(f"  FAIL {name}")

    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS demo_items"))
        conn.execute(text("DROP TABLE IF EXISTS demo_doctors"))

    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
