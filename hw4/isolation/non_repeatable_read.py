from sqlalchemy import text

from isolation.common import balance, connect, reset_accounts, verdict


def demo(level: str) -> None:
    reset_accounts(("alice", 100))
    print(f"\n# non-repeatable read, A: {level}")

    with connect(level) as a, connect("READ COMMITTED") as b:
        first = balance(a, "alice")
        print(f"A: balance = {first}")
        b.execute(text("UPDATE accounts SET balance = 50 WHERE owner = 'alice'"))
        b.commit()
        print("B: balance = 50, commit")
        second = balance(a, "alice")
        print(f"A: balance = {second}")
        a.commit()

    print(verdict(first != second))


def main() -> None:
    demo("READ COMMITTED")
    demo("REPEATABLE READ")


if __name__ == "__main__":
    main()
