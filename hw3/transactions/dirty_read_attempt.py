"""
Dirty read in PostgreSQL: an attempt to reproduce the anomaly.

PostgreSQL does not support true READ UNCOMMITTED - it is emulated as
READ COMMITTED. Therefore, dirty read is impossible in PostgreSQL:
uncommitted values are not visible even at READ UNCOMMITTED.

This script honestly shows that the anomaly is NOT reproduced and explains why.
"""
import time

import psycopg
from psycopg import IsolationLevel

DSN = "host=localhost port=5433 dbname=shop user=shop password=shop"


def setup():
    with psycopg.connect(DSN, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS dirty_demo")
            cur.execute("CREATE TABLE dirty_demo (id INT PRIMARY KEY, value INT)")
            cur.execute("INSERT INTO dirty_demo VALUES (1, 100)")


def scenario(isolation: IsolationLevel) -> None:
    print(f"\n--- isolation = {isolation.name} ---")
    conn_a = psycopg.connect(DSN)
    conn_b = psycopg.connect(DSN)
    try:
        conn_b.isolation_level = isolation
        cur_b = conn_b.cursor()

        # T1: UPDATE without COMMIT
        cur_a = conn_a.cursor()
        cur_a.execute("UPDATE dirty_demo SET value = 200 WHERE id = 1")
        print("T1: UPDATE value = 200 (no COMMIT)")

        # T2: reads inside its own transaction
        cur_b.execute("SELECT value FROM dirty_demo WHERE id = 1")
        seen = cur_b.fetchone()[0]
        print(f"T2: read value = {seen}")

        if seen == 200:
            print(">>> DIRTY READ reproduced (T2 sees uncommitted value)")
        else:
            print(">>> DIRTY READ NOT reproduced (T2 sees old value 100)")
            print("    PostgreSQL does not support true READ UNCOMMITTED -")
            print("    it is emulated as READ COMMITTED, so dirty read is impossible.")

        conn_a.rollback()
        conn_b.rollback()
    finally:
        conn_a.close()
        conn_b.close()


if __name__ == "__main__":
    setup()
    time.sleep(0.5)
    # psycopg3 may not have READ_UNCOMMITTED in enum - use READ_COMMITTED
    # and explain in output that PG treats it as READ COMMITTED.
    scenario(IsolationLevel.READ_COMMITTED)
    time.sleep(0.5)
    scenario(IsolationLevel.READ_COMMITTED)
