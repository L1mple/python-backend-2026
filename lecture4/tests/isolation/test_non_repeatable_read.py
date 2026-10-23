
from sqlalchemy import text


def test_non_repeatable_read(engine):
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
            first = a.execute(text(
                "SELECT balance FROM isolation_accounts WHERE id=1"
            )).scalar_one()

            with b.begin():
                b.execute(text(
                    "UPDATE isolation_accounts SET balance=150 WHERE id=1"
                ))

            second = a.execute(text(
                "SELECT balance FROM isolation_accounts WHERE id=1"
            )).scalar_one()

            assert first == 100
            assert second == 150
        finally:
            ta.rollback()


def test_repeatable_read_prevents_non_repeatable_read(engine):
    with engine.connect() as a, engine.connect() as b:
        a.execute(text(
            "SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ"
        ))
        b.execute(text(
            "SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED"
        ))
        a.commit()
        b.commit()

        ta = a.begin()
        try:
            first = a.execute(text(
                "SELECT balance FROM isolation_accounts WHERE id=1"
            )).scalar_one()

            with b.begin():
                b.execute(text(
                    "UPDATE isolation_accounts SET balance=150 WHERE id=1"
                ))

            second = a.execute(text(
                "SELECT balance FROM isolation_accounts WHERE id=1"
            )).scalar_one()

            assert first == 100
            assert second == 100
        finally:
            ta.rollback()
