"""
Демонстрация non-repeatable read.

- При READ COMMITTED: повторное чтение в той же транзакции A видит уже
  закоммиченное изменение B - значение "уехало" по сравнению с первым
  чтением.
- При REPEATABLE READ: повторное чтение в той же транзакции видит то же
  самое значение, что и в первый раз (снэпшот транзакции не меняется).

Запуск (нужен поднятый MySQL - см. hw4/README.md), из корня репозитория:

    python -m hw4.isolation_demos.non_repeatable_read
"""
import threading

from ._db import connect, ensure_demo_schema, reset_accounts
from ._sync import StepSync


def _run(isolation_level: str) -> None:
    print(f"\n=== {isolation_level} ===")
    reset_accounts(balance=1000)
    sync = StepSync()
    reads: list[int] = []

    def session_a() -> None:
        conn = connect(isolation_level)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT balance FROM demo_accounts WHERE id = 1")
                first = cur.fetchone()[0]
                reads.append(first)
                print(f"[A] первое чтение:  balance = {first}")

                sync.signal("a_read_1")
                sync.wait("b_committed")

                cur.execute("SELECT balance FROM demo_accounts WHERE id = 1")
                second = cur.fetchone()[0]
                reads.append(second)
                print(f"[A] второе чтение:  balance = {second}")
            conn.commit()
        finally:
            conn.close()

    def session_b() -> None:
        sync.wait("a_read_1")
        conn = connect()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE demo_accounts SET balance = balance - 100 WHERE id = 1")
            conn.commit()
            print("[B] UPDATE balance -= 100 + COMMIT")
        finally:
            conn.close()
        sync.signal("b_committed")

    ta = threading.Thread(target=session_a)
    tb = threading.Thread(target=session_b)
    ta.start()
    tb.start()
    ta.join()
    tb.join()

    changed = reads[0] != reads[1]
    label = "ДА, non-repeatable read произошёл" if changed else "НЕТ, второе чтение совпало с первым"
    print(f"[Результат] {label} ({reads[0]} -> {reads[1]})")


def main() -> None:
    ensure_demo_schema()
    _run("READ COMMITTED")
    _run("REPEATABLE READ")


if __name__ == "__main__":
    main()
