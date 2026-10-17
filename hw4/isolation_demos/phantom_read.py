"""
Демонстрация phantom read.

ВАЖНО (особенность InnoDB/MySQL): обычный (неблокирующий) SELECT под
REPEATABLE READ в InnoDB видит консистентный снэпшот, сделанный на момент
первого чтения транзакции, и поэтому "не замечает" новые строки, вставленные
и закоммиченные другой транзакцией - это сильнее классического определения
REPEATABLE READ из стандарта SQL (где фантомы ещё разрешены).

Чтобы всё равно показать реальный фантом при REPEATABLE READ, транзакция A
сначала делает SELECT COUNT(...), а затем, в той же транзакции - UPDATE по
тому же условию. UPDATE в InnoDB - это "текущее" чтение (current read), а
не чтение по снэпшоту, поэтому он видит уже закоммиченные новые строки,
даже если их не было в предыдущем SELECT. Расхождение между количеством из
SELECT и числом строк, затронутых UPDATE - и есть фантом.

При SERIALIZABLE обычный SELECT в InnoDB неявно становится блокирующим
(как SELECT ... LOCK IN SHARE MODE) и берёт gap-лок на диапазон. Поэтому
INSERT из другой транзакции в этот диапазон не может "проскочить" - он
просто блокируется и ждёт, пока A не завершит транзакцию. Фантом физически
не может возникнуть.

Запуск (нужен поднятый MySQL - см. hw4/README.md), из корня репозитория:

    python -m hw4.isolation_demos.phantom_read
"""
import threading
import time

from ._db import connect, ensure_demo_schema, reset_products
from ._sync import StepSync


def _run_repeatable_read() -> None:
    print("\n=== REPEATABLE READ ===")
    reset_products([50, 150])
    sync = StepSync()
    state: dict[str, int] = {}

    def session_a() -> None:
        conn = connect("REPEATABLE READ")
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM demo_products WHERE price > 100")
                before = cur.fetchone()[0]
                state["select_count"] = before
                print(f"[A] SELECT COUNT(price > 100) = {before}")

                sync.signal("a_selected")
                sync.wait("b_inserted")

                cur.execute("UPDATE demo_products SET price = price + 1 WHERE price > 100")
                affected = cur.rowcount
                state["update_count"] = affected
                print(f"[A] UPDATE price>100 затронул {affected} строк(и)")
            conn.commit()
        finally:
            conn.close()

    def session_b() -> None:
        sync.wait("a_selected")
        conn = connect()
        try:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO demo_products (price) VALUES (200)")
            conn.commit()
            print("[B] INSERT price=200 + COMMIT")
        finally:
            conn.close()
        sync.signal("b_inserted")

    ta = threading.Thread(target=session_a)
    tb = threading.Thread(target=session_b)
    ta.start()
    tb.start()
    ta.join()
    tb.join()

    phantom = state["update_count"] > state["select_count"]
    label = "ДА, фантом произошёл" if phantom else "НЕТ, фантома не было"
    print(
        f"[Результат] {label}: SELECT увидел {state['select_count']} строк(и), "
        f"а UPDATE затронул {state['update_count']} (новая строка B 'появилась' для записи)"
    )


def _run_serializable() -> None:
    print("\n=== SERIALIZABLE ===")
    reset_products([50, 150])
    sync = StepSync()
    timings: dict[str, float] = {}

    def session_a() -> None:
        conn = connect("SERIALIZABLE")
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM demo_products WHERE price > 100")
                before = cur.fetchone()[0]
                print(f"[A] SELECT COUNT(price > 100) = {before} (неявно блокирующий под SERIALIZABLE)")

                sync.signal("a_selected")
                # Даём B время попытаться вставить - он должен заблокироваться.
                time.sleep(1.5)
                timings["a_before_commit"] = time.monotonic()
            conn.commit()
            print("[A] COMMIT (теперь B может продолжить)")
        finally:
            conn.close()

    def session_b() -> None:
        sync.wait("a_selected")
        conn = connect()
        try:
            with conn.cursor() as cur:
                start = time.monotonic()
                cur.execute("INSERT INTO demo_products (price) VALUES (200)")
                timings["b_insert_returned"] = time.monotonic()
            conn.commit()
            print(
                f"[B] INSERT закончился через {timings['b_insert_returned'] - start:.2f}с "
                "(ждал, пока A не закоммитит)"
            )
        finally:
            conn.close()

    ta = threading.Thread(target=session_a)
    tb = threading.Thread(target=session_b)
    ta.start()
    tb.start()
    ta.join()
    tb.join()

    blocked = timings["b_insert_returned"] > timings["a_before_commit"]
    label = "ДА, B был заблокирован до коммита A" if blocked else "НЕТ, B не блокировался"
    print(f"[Результат] {label} -> фантом невозможен, т.к. вставка не могла произойти параллельно")


def main() -> None:
    ensure_demo_schema()
    _run_repeatable_read()
    _run_serializable()


if __name__ == "__main__":
    main()
