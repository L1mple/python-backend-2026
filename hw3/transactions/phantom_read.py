"""
Phantom read: within one transaction we read a set of rows twice and get different counts.

We show:
  1) at REPEATABLE READ - in PostgreSQL phantom read is NOT reproduced (snapshot isolation);
  2) at SERIALIZABLE - also not reproduced.

This matches the README: in PostgreSQL phantom read cannot be demonstrated.
"""
import time

import psycopg
from psycopg import IsolationLevel

DSN = "host=localhost port=5433 dbname=shop user=shop password=shop"


def setup():
    with psycopg.connect(DSN, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS phantom_demo")
            cur.execute("CREATE TABLE phantom_demo (id SERIAL PRIMARY KEY, value INT)")
            cur.execute("INSERT INTO phantom_demo (value) VALUES (10), (20)")


def scenario(isolation: IsolationLevel) -> None:
    print(f"\n--- isolation = {isolation.name} ---")
    conn_a = psycopg.connect(DSN)
    conn_b = psycopg.connect(DSN)
    try:
        conn_a.isolation_level = isolation
        cur_a = conn_a.cursor()

        cur_a.execute("SELECT COUNT(*) FROM phantom_demo WHERE value > 0")
        first = cur_a.fetchone()[0]
        print(f"T1: first read count = {first}")

        with conn_b.cursor() as cur_b:
            cur_b.execute("INSERT INTO phantom_demo (value) VALUES (30)")
        conn_b.commit()
        print("T2: INSERT value = 30 and COMMIT")

        cur_a.execute("SELECT COUNT(*) FROM phantom_demo WHERE value > 0")
        second = cur_a.fetchone()[0]
        print(f"T1: second read count = {second}")

        if first != second:
            print(">>> PHANTOM READ reproduced (counts differ)")
        else:
            print(">>> phantom read is GONE (counts are the same)")

        conn_a.rollback()
    finally:
        conn_a.close()
        conn_b.close()


if __name__ == "__main__":
    setup()
    time.sleep(0.5)
    scenario(IsolationLevel.REPEATABLE_READ)

    setup()
    time.sleep(0.5)
    scenario(IsolationLevel.SERIALIZABLE)
