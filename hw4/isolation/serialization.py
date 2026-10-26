# Write skew: sum of balances must stay >= 0. Each transaction checks the sum
# and withdraws 150 from its own account, together they go below zero.
from psycopg.errors import SerializationFailure
from sqlalchemy import Connection, text
from sqlalchemy.exc import OperationalError

from isolation.common import connect, reset_accounts, verdict
from store.db import engine


def total(conn: Connection) -> int:
    return conn.execute(text("SELECT sum(balance) FROM accounts")).scalar_one()


def withdraw(conn: Connection, owner: str) -> None:
    conn.execute(
        text("UPDATE accounts SET balance = balance - 150 WHERE owner = :owner"),
        {"owner": owner},
    )


def demo(level: str) -> None:
    reset_accounts(("alice", 100), ("bob", 100))
    print(f"\n# write skew, A и B: {level}")

    with connect(level) as a, connect(level) as b:
        print(f"A: sum = {total(a)}, снимает 150 с alice")
        print(f"B: sum = {total(b)}, снимает 150 с bob")
        withdraw(a, "alice")
        withdraw(b, "bob")
        a.commit()
        try:
            b.commit()
            print("B: commit")
        except OperationalError as error:
            if not isinstance(error.orig, SerializationFailure):
                raise
            print("B: commit отклонён, SerializationFailure")

    with engine.connect() as conn:
        final = total(conn)
    print(f"итоговая сумма = {final}")
    print(verdict(final < 0))


def main() -> None:
    demo("REPEATABLE READ")
    demo("SERIALIZABLE")


if __name__ == "__main__":
    main()
