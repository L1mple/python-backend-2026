from sqlalchemy import text
from shop_api.dbase import engine


def reset():
    with engine.begin() as db:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS test_tab (
                id INTEGER PRIMARY KEY,
                value INTEGER
            )
        """))
        db.execute(text("DELETE FROM test_tab"))
        db.execute(text("INSERT INTO test_tab VALUES (1, 100)"))


def dirty():
    for lvl in ["READ UNCOMMITTED", "READ COMMITTED"]:
        reset()

        with engine.connect() as b:
            b.execute(text("UPDATE test_tab SET value = 200 WHERE id = 1"))

            with engine.connect().execution_options(isolation_level=lvl) as a:
                val = a.execute(text("SELECT value FROM test_tab WHERE id = 1")).scalar()

            b.rollback()
        print("Dirty:", lvl, val)


def repeat():
    for lvl in ["READ COMMITTED", "REPEATABLE READ"]:
        reset()
        with engine.connect().execution_options(isolation_level=lvl) as a:
            x = a.execute(text("SELECT value FROM test_tab WHERE id = 1")).scalar()

            with engine.begin() as b:
                b.execute(text("UPDATE test_tab SET value = 200 WHERE id = 1"))

            y = a.execute(text("SELECT value FROM test_tab WHERE id = 1")).scalar()

        print("Repeat:", lvl, x, y)


def phantom():
    for lvl in ["READ COMMITTED", "REPEATABLE READ", "SERIALIZABLE"]:
        reset()

        with engine.connect().execution_options(isolation_level=lvl) as a:
            x = a.execute(text("SELECT COUNT(*) FROM test_tab")).scalar()

            with engine.begin() as b:
                b.execute(text("INSERT INTO test_tab VALUES (2, 200)"))

            y = a.execute(text("SELECT COUNT(*) FROM test_tab")).scalar()
        print("Phantom:", lvl, x, y)


dirty()
repeat()
phantom()