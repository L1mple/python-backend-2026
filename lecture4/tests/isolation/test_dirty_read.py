
from sqlalchemy import text


def test_dirty_read(engine):
    with engine.connect() as a, engine.connect() as b:
        a.execute(text(
            "SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED"
        ))
        b.execute(text(
            "SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED"
        ))
        a.commit()
        b.commit()

        ta = a.begin()
        try:
            a.execute(text(
                "UPDATE isolation_accounts SET balance=999 WHERE id=1"
            ))

            tb = b.begin()
            try:
                value = b.execute(text(
                    "SELECT balance FROM isolation_accounts WHERE id=1"
                )).scalar_one()
                assert value == 999
            finally:
                tb.rollback()
        finally:
            ta.rollback()


def test_read_committed_prevents_dirty_read(engine):
    with engine.connect() as a, engine.connect() as b:
        a.execute(text(
            "SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED"
        ))
        b.execute(text(
            "SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED"
        ))
        a.commit()
        b.commit()

        ta = a.begin()
        try:
            a.execute(text(
                "UPDATE isolation_accounts SET balance=999 WHERE id=1"
            ))

            tb = b.begin()
            try:
                value = b.execute(text(
                    "SELECT balance FROM isolation_accounts WHERE id=1"
                )).scalar_one()
                assert value == 100
            finally:
                tb.rollback()
        finally:
            ta.rollback()
