import threading

from sqlalchemy import create_engine, text

engine = create_engine("postgresql+psycopg2://shop:shop@localhost:5432/shop")

with engine.begin() as conn:
    conn.execute(text("drop table if exists account"))
    conn.execute(text("create table account (id int primary key, balance int)"))
    conn.execute(text("insert into account values (1, 100)"))

started = threading.Event()
checked = threading.Event()
found = {}


def writer():
    conn = engine.connect().execution_options(isolation_level="READ COMMITTED")
    conn.execute(text("update account set balance = 999 where id = 1"))
    started.set()
    checked.wait()
    conn.rollback()
    conn.close()


def reader():
    started.wait()
    conn = engine.connect().execution_options(isolation_level="READ COMMITTED")
    found["balance"] = conn.execute(text("select balance from account where id = 1")).scalar()
    checked.set()
    conn.close()


t1 = threading.Thread(target=writer)
t2 = threading.Thread(target=reader)
t1.start()
t2.start()
t1.join()
t2.join()

print("found balance:", found["balance"])
