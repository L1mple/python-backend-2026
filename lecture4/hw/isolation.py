import os

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

engine = create_engine(
    os.getenv("DATABASE_URL", "mysql+pymysql://root:password@localhost:3307/hw4_db")
)

SELECT_BALANCE = text("SELECT balance FROM accounts WHERE id = 1")
COUNT_ROWS = text("SELECT COUNT(*) FROM accounts")


def reset():
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS accounts"))
        conn.execute(text("CREATE TABLE accounts (id INT AUTO_INCREMENT PRIMARY KEY, balance INT)"))
        conn.execute(text("INSERT INTO accounts (balance) VALUES (100), (200)"))


def connect(level):
    return engine.connect().execution_options(isolation_level=level)


def dirty_read(level):
    reset()
    with connect(level) as a, connect(level) as b:
        a.execute(text("UPDATE accounts SET balance = 0 WHERE id = 1"))
        print(f"{level}: B видит баланс {b.execute(SELECT_BALANCE).scalar()} (A ещё не сделал commit, было 100)")
        a.rollback()


def non_repeatable_read(level):
    reset()
    with connect(level) as a, connect(level) as b:
        print(f"{level}: A читает баланс {a.execute(SELECT_BALANCE).scalar()}")
        b.execute(text("UPDATE accounts SET balance = 500 WHERE id = 1"))
        b.commit()
        print(f"{level}: A читает снова {a.execute(SELECT_BALANCE).scalar()} (B поменял на 500 и сделал commit)")


def phantom_read(level):
    reset()
    with connect(level) as a, connect(level) as b:
        print(f"{level}: A считает строки: {a.execute(COUNT_ROWS).scalar()}")
        b.execute(text("INSERT INTO accounts (balance) VALUES (300)"))
        b.commit()
        print(f"{level}: A считает снова: {a.execute(COUNT_ROWS).scalar()} (B добавил строку и сделал commit)")
        a.execute(text("UPDATE accounts SET balance = balance + 1"))
        print(f"{level}: A обновил все строки и считает: {a.execute(COUNT_ROWS).scalar()}")


def phantom_read_serializable(level):
    reset()
    with connect(level) as a, connect(level) as b:
        print(f"{level}: A считает строки: {a.execute(COUNT_ROWS).scalar()}")
        b.execute(text("SET SESSION innodb_lock_wait_timeout = 2"))
        try:
            b.execute(text("INSERT INTO accounts (balance) VALUES (300)"))
            print(f"{level}: B вставил строку, фантом возможен")
        except OperationalError:
            print(f"{level}: B не смог вставить строку, пока A не закончил (фантома нет)")
        print(f"{level}: A считает снова: {a.execute(COUNT_ROWS).scalar()}")


print("1. Dirty read есть при READ UNCOMMITTED")
dirty_read("READ UNCOMMITTED")

print("\n2. Dirty read нет при READ COMMITTED")
dirty_read("READ COMMITTED")

print("\n3. Non-repeatable read есть при READ COMMITTED")
non_repeatable_read("READ COMMITTED")

print("\n4. Non-repeatable read нет при REPEATABLE READ")
non_repeatable_read("REPEATABLE READ")

print("\n5. Phantom read есть при REPEATABLE READ")
phantom_read("REPEATABLE READ")

print("\n6. Phantom read нет при SERIALIZABLE")
phantom_read_serializable("SERIALIZABLE")
