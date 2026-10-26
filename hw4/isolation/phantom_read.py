from sqlalchemy import Connection, text

from isolation.common import connect, reset_accounts, verdict


def count_rich(conn: Connection) -> int:
    return conn.execute(
        text("SELECT count(*) FROM accounts WHERE balance >= 100")
    ).scalar_one()


def demo(level: str) -> None:
    reset_accounts(("alice", 100), ("bob", 200))
    print(f"\n# phantom read, A: {level}")

    with connect(level) as a, connect("READ COMMITTED") as b:
        first = count_rich(a)
        print(f"A: count(balance >= 100) = {first}")
        b.execute(text("INSERT INTO accounts (owner, balance) VALUES ('carol', 300)"))
        b.commit()
        print("B: insert carol, commit")
        second = count_rich(a)
        print(f"A: count(balance >= 100) = {second}")
        a.commit()

    print(verdict(first != second))


def main() -> None:
    demo("READ COMMITTED")
    demo("REPEATABLE READ")
    demo("SERIALIZABLE")


if __name__ == "__main__":
    main()
