from sqlalchemy import text

from isolation.common import balance, connect, reset_accounts, verdict


def demo(level: str) -> None:
    reset_accounts(("alice", 100))
    print(f"\n# dirty read, A: {level}")

    with connect(level) as a, connect("READ COMMITTED") as b:
        real = a.execute(text("SHOW transaction_isolation")).scalar_one()
        print(f"A: уровень в postgres = {real}")
        b.execute(text("UPDATE accounts SET balance = 0 WHERE owner = 'alice'"))
        print("B: balance = 0, без commit")
        seen = balance(a, "alice")
        print(f"A: balance = {seen}")
        b.rollback()
        a.commit()

    print(verdict(seen == 0))


def main() -> None:
    demo("READ UNCOMMITTED")
    demo("READ COMMITTED")


if __name__ == "__main__":
    main()
