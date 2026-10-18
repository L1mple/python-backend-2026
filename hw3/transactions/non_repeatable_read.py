"""
Non-repeatable read: within one transaction we read a row twice and get different values.

We show:
  1) at READ COMMITTED - non-repeatable read is reproduced;
  2) at REPEATABLE READ - it is gone.
"""
import time

import psycopg
from psycopg import IsolationLevel

DSN = "host=localhost port=5433 dbname=shop user=shop password=shop"


def setup():
    with psycopg.connect(DSN, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS nrr_demo")
            cur.execute("CREATE TABLE nrr_demo (id INT PRIMARY KEY, value INT)")
            cur.execute("INSERT INTO nrr_demo VALUES (1, 100)")


def scenario(isolation: IsolationLevel) -> None:
    print(f"\n--- isolation = {isolation.name} ---")
    conn_a = psycopg.connect(DSN)
    conn_b = psycopg.connect(DSN)
    try:
        conn_a.isolation_level = isolation
        cur_a = conn_a.cursor()

        cur_a.execute("SELECT value FROM nrr_demo WHERE id = 1")
        first = cur_a.fetchone()[0]
        print(f"T1: first read value = {first}")

        with conn_b.cursor() as cur_b:
            cur_b.execute("UPDATE nrr_demo SET value = 200 WHERE id = 1")
        conn_b.commit()
        print("T2: UPDATE value = 200 and COMMIT")

        cur_a.execute("SELECT value FROM nrr_demo WHERE id = 1")
        second = cur_a.fetchone()[0]
        print(f"T1: second read value = {second}")

        if first != second:
            print(">>> NON-REPEATABLE READ reproduced (values differ)")
        else:
            print(">>> non-repeatable read is GONE (values are the same)")

        conn_a.rollback()
    finally:
        conn_a.close()
        conn_b.close()


if __name__ == "__main__":
    # setup() перед каждым сценарием, чтобы каждый начинал с чистого значения 100
    setup()
    time.sleep(0.5)
    scenario(IsolationLevel.READ_COMMITTED)

    setup()
    time.sleep(0.5)
    scenario(IsolationLevel.REPEATABLE_READ)
