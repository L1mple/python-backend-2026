
import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError


def test_repeatable_read_prevents_phantom_in_consistent_read(engine):
    with engine.begin() as conn:
        conn.execute(text(
            "DELETE FROM isolation_accounts WHERE id >= 10"
        ))

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
                "SELECT id FROM isolation_accounts WHERE id >= 10"
            )).scalars().all()

            with b.begin():
                b.execute(text(
                    "INSERT INTO isolation_accounts (id, balance) "
                    "VALUES (10, 300)"
                ))

            second = a.execute(text(
                "SELECT id FROM isolation_accounts WHERE id >= 10"
            )).scalars().all()

            assert first == []
            assert second == []
        finally:
            ta.rollback()


def test_serializable_blocks_phantom_insert(engine):
    with engine.begin() as conn:
        conn.execute(text(
            "DELETE FROM isolation_accounts WHERE id >= 10"
        ))

    with engine.connect() as a, engine.connect() as b:
        a.execute(text(
            "SET SESSION TRANSACTION ISOLATION LEVEL SERIALIZABLE"
        ))
        b.execute(text(
            "SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED"
        ))
        b.execute(text("SET SESSION innodb_lock_wait_timeout = 2"))
        a.commit()
        b.commit()

        ta = a.begin()
        try:
            first = a.execute(text(
                "SELECT id FROM isolation_accounts WHERE id >= 10"
            )).scalars().all()
            assert first == []

            tb = b.begin()
            try:
                with pytest.raises(OperationalError):
                    b.execute(text(
                        "INSERT INTO isolation_accounts (id, balance) "
                        "VALUES (10, 300)"
                    ))
            finally:
                tb.rollback()

            second = a.execute(text(
                "SELECT id FROM isolation_accounts WHERE id >= 10"
            )).scalars().all()
            assert second == []
        finally:
            ta.rollback()
