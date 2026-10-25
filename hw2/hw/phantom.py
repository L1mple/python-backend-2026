import threading

from sqlalchemy import create_engine, text

engine = create_engine("postgresql+psycopg2://shop:shop@localhost:5432/shop")

for level in ["READ COMMITTED", "REPEATABLE READ", "SERIALIZABLE"]:
    with engine.begin() as conn:
        conn.execute(text("drop table if exists product"))
        conn.execute(text("create table product (id int primary key, price int)"))
        conn.execute(text("insert into product values (1, 10), (2, 20)"))

    first_done = threading.Event()
    inserted = threading.Event()
    found = {}

    def reader():
        conn = engine.connect().execution_options(isolation_level=level)
        found["first"] = conn.execute(text("select count(*) from product")).scalar()
        first_done.set()
        inserted.wait()
        found["second"] = conn.execute(text("select count(*) from product")).scalar()
        conn.rollback()
        conn.close()

    def writer():
        first_done.wait()
        conn = engine.connect()
        conn.execute(text("insert into product values (3, 30)"))
        conn.commit()
        conn.close()
        inserted.set()

    t1 = threading.Thread(target=reader)
    t2 = threading.Thread(target=writer)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    print(level, found["first"], found["second"])
