import os
import sys
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://shop:shop@localhost:5432/shop"
)
engine = create_engine(DATABASE_URL)


@contextmanager
def tx(level: str):
    conn = engine.connect().execution_options(isolation_level=level)
    try:
        yield conn
    finally:
        conn.close()


def reset():
    with engine.begin() as c:
        c.execute(text("DROP TABLE IF EXISTS iso_demo"))
        c.execute(
            text(
                "CREATE TABLE iso_demo ("
                " id serial PRIMARY KEY, kind text NOT NULL, value int NOT NULL)"
            )
        )
        c.execute(text("INSERT INTO iso_demo (kind, value) VALUES ('acc', 100)"))


def balance(c) -> int:
    return c.execute(text("SELECT value FROM iso_demo WHERE kind='acc'")).scalar_one()


def count(c, kind: str) -> int:
    return c.execute(
        text("SELECT count(*) FROM iso_demo WHERE kind=:k"), {"k": kind}
    ).scalar_one()


_results: list[bool] = []


def check(ok: bool, msg: str):
    _results.append(ok)
    print(f"  {'PASSED: ' if ok else 'FAILED: '} {msg}")


def title(s: str):
    print(f"\n=== {s} ===")


# ---------- сценарии ----------

def dirty_read(level: str) -> int:
    """B меняет баланс, но не коммитит. Что видит A?"""
    reset()
    with tx(level) as a, tx(level) as b:
        b.execute(text("UPDATE iso_demo SET value = 200 WHERE kind='acc'"))
        seen = balance(a)
        b.rollback()
    return seen


def non_repeatable_read(level: str) -> tuple[int, int]:
    """A читает строку дважды, между чтениями B меняет её и коммитит."""
    reset()
    with tx(level) as a:
        first = balance(a)
        with tx("READ COMMITTED") as b:
            b.execute(text("UPDATE iso_demo SET value = 200 WHERE kind='acc'"))
            b.commit()
        second = balance(a)
    return first, second


def phantom_read(level: str) -> tuple[int, int]:
    """A дважды считает строки по условию, между чтениями B вставляет новую строку."""
    reset()
    with tx(level) as a:
        first = count(a, "acc")
        with tx("READ COMMITTED") as b:
            b.execute(text("INSERT INTO iso_demo (kind, value) VALUES ('acc', 50)"))
            b.commit()
        second = count(a, "acc")
    return first, second


def write_skew(level: str) -> tuple[int, list[tuple[str, str]]]:
    """
    Инвариант: строк kind='promo' должно быть не больше одной.
    Обе транзакции проверяют count == 0 и вставляют свою строку.
    Вставка соседа для каждой - "фантом", из-за которого проверка устарела.
    """
    reset()
    errors: list[tuple[str, str]] = []
    with tx(level) as a, tx(level) as b:
        assert count(a, "promo") == 0
        assert count(b, "promo") == 0
        for name, c in (("A", a), ("B", b)):
            try:
                c.execute(text("INSERT INTO iso_demo (kind, value) VALUES ('promo', 1)"))
                c.commit()
            except DBAPIError as e:
                c.rollback()
                errors.append((name, getattr(e.orig, "pgcode", "?")))
    with engine.connect() as c:
        return count(c, "promo"), errors


def main():
    title("1. Dirty read")
    for level in ("READ UNCOMMITTED", "READ COMMITTED"):
        seen = dirty_read(level)
        check(
            seen == 100,
            f"{level}: A видит {seen} (B записал 200 без commit) -> грязного чтения нет"
            + (" [в PG READ UNCOMMITTED ведёт себя как READ COMMITTED]"
               if level == "READ UNCOMMITTED" else ""),
        )

    title("2. Non-repeatable read")
    first, second = non_repeatable_read("READ COMMITTED")
    check(first != second, f"READ COMMITTED: {first} -> {second}, аномалия ВОСПРОИЗВЕДЕНА")
    first, second = non_repeatable_read("REPEATABLE READ")
    check(first == second, f"REPEATABLE READ: {first} -> {second}, чтение повторяемо")

    title("3. Phantom read")
    first, second = phantom_read("READ COMMITTED")
    check(first != second, f"READ COMMITTED: count {first} -> {second}, фантом ВОСПРОИЗВЕДЁН")
    first, second = phantom_read("REPEATABLE READ")
    check(
        first == second,
        f"REPEATABLE READ: count {first} -> {second}; в PG фантомов нет "
        "(snapshot isolation строже стандарта)",
    )

    title("4. Аномалия, связанная с фантомами (write skew): RR vs SERIALIZABLE")
    total, errors = write_skew("REPEATABLE READ")
    check(total == 2 and not errors,
          f"REPEATABLE READ: в таблице {total} promo-строк (инвариант <=1 нарушен)")
    total, errors = write_skew("SERIALIZABLE")
    check(
        total == 1 and errors and all(code == "40001" for _, code in errors),
        f"SERIALIZABLE: в таблице {total} promo-строк, ошибки {errors} "
        "(40001 serialization_failure -> транзакцию нужно повторить)",
    )

    with engine.begin() as c:
        c.execute(text("DROP TABLE IF EXISTS iso_demo"))


if __name__ == "__main__":
    main()