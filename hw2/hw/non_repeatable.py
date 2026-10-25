import threading

from sqlalchemy import create_engine, text

engine = create_engine("postgresql+psycopg2://shop:shop@localhost:5432/shop")

for level in ["READ COMMITTED", "REPEATABLE READ"]:
    with engine.begin() as conn:
        conn.execute(text("drop table if exists account"))
        conn.execute(text("create table account (id int primary key, balance int)"))
        conn.execute(text("insert into account values (1, 100)"))

    first_done = threading.Event()
    updated = threading.Event()
    found = {}

    def reader():
        conn = engine.connect().execution_options(isolation_level=level)
        found["first"] = conn.execute(text("select balance from account where id = 1")).scalar()
        first_done.set()
        updated.wait()
        found["second"] = conn.execute(text("select balance from account where id = 1")).scalar()
        conn.rollback()
        conn.close()

    def writer():
        first_done.wait()
        conn = engine.connect()
        conn.execute(text("update account set balance = 500 where id = 1"))
        conn.commit()
        conn.close()
        updated.set()

    t1 = threading.Thread(target=reader)
    t2 = threading.Thread(target=writer)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    print(level, found["first"], found["second"])
