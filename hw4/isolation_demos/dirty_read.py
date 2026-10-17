"""
Демонстрация dirty read.

- При READ UNCOMMITTED: транзакция A видит ещё не закоммиченное (и в итоге
  откатываемое) изменение транзакции B.
- При READ COMMITTED: тот же сценарий, но A видит только закоммиченные
  данные - B пока не закоммитил, значит A ничего не замечает.

Запуск (нужен поднятый MySQL - см. hw4/README.md), из корня репозитория:

    python -m hw4.isolation_demos.dirty_read
"""
import threading

from ._db import connect, ensure_demo_schema, reset_accounts
from ._sync import StepSync


def _run(isolation_level: str) -> None:
    print(f"\n=== {isolation_level} ===")
    reset_accounts(balance=1000)
    sync = StepSync()
    seen_during: list[int] = []

    def session_a() -> None:
        conn = connect(isolation_level)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT balance FROM demo_accounts WHERE id = 1")
                before = cur.fetchone()[0]
                print(f"[A] до изменения B:        balance = {before}")

                sync.signal("a_read_before")
                sync.wait("b_updated")

                cur.execute("SELECT balance FROM demo_accounts WHERE id = 1")
                during = cur.fetchone()[0]
                seen_during.append(during)
                print(f"[A] пока B не закоммитил:  balance = {during}")

                sync.signal("a_read_during")
            conn.commit()
        finally:
            conn.close()

    def session_b() -> None:
        sync.wait("a_read_before")
        conn = connect()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE demo_accounts SET balance = balance - 100 WHERE id = 1")
            print("[B] UPDATE balance -= 100 (ещё без COMMIT)")
            sync.signal("b_updated")

            sync.wait("a_read_during")
            # Откатываем: это изменение никогда не должно было стать "настоящим".
            conn.rollback()
            print("[B] ROLLBACK (изменение отменено)")
        finally:
            conn.close()

    ta = threading.Thread(target=session_a)
    tb = threading.Thread(target=session_b)
    ta.start()
    tb.start()
    ta.join()
    tb.join()

    dirty_read_happened = seen_during[0] == 900
    label = "ДА, грязное чтение произошло" if dirty_read_happened else "НЕТ, грязного чтения не было"
    print(f"[Результат] {label} (A увидел balance={seen_during[0]} ещё до коммита B)")


def main() -> None:
    ensure_demo_schema()
    _run("READ UNCOMMITTED")
    _run("READ COMMITTED")


if __name__ == "__main__":
    main()
