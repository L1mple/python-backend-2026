from threading import Event, Thread

from sqlalchemy import create_engine, text

from database import DATABASE_URL


engine = create_engine(DATABASE_URL)


def prepare():
    with engine.begin() as db:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS tx_demo (
                id INT PRIMARY KEY,
                price INT NOT NULL,
                INDEX idx_price (price)
            ) ENGINE=InnoDB
        """))

        db.execute(text("DELETE FROM tx_demo"))
        db.execute(text(
            "INSERT INTO tx_demo (id, price) VALUES (1, 100)"
        ))


def read_price(conn):
    return conn.execute(
        text("SELECT price FROM tx_demo WHERE id = 1")
    ).scalar_one()


def count_expensive(conn):
    return conn.execute(
        text("SELECT COUNT(*) FROM tx_demo WHERE price > 100")
    ).scalar_one()


# 1. DIRTY READ

def dirty_read(level):
    prepare()

    with engine.connect() as writer:
        with writer.begin() as tx:
            writer.execute(text(
                "UPDATE tx_demo SET price = 900 WHERE id = 1"
            ))

            with engine.connect().execution_options(
                isolation_level=level
            ) as reader:
                with reader.begin():
                    value = read_price(reader)

            tx.rollback()

    expected = 900 if level == "READ UNCOMMITTED" else 100
    assert value == expected

    print(f"Dirty read [{level}]: {value}")


# 2. NON-REPEATABLE READ

def non_repeatable_read(level):
    prepare()

    with engine.connect().execution_options(
        isolation_level=level
    ) as reader:

        with reader.begin():
            first = read_price(reader)

            with engine.begin() as writer:
                writer.execute(text(
                    "UPDATE tx_demo SET price = 200 WHERE id = 1"
                ))

            second = read_price(reader)

    expected = 200 if level == "READ COMMITTED" else 100
    assert first == 100 and second == expected

    print(f"Non-repeatable read [{level}]: {first} -> {second}")


# 3. PHANTOM READ

def phantom_read(level):
    prepare()

    with engine.connect().execution_options(
        isolation_level=level
    ) as reader:

        with reader.begin():
            first = count_expensive(reader)

            with engine.begin() as writer:
                writer.execute(text(
                    "INSERT INTO tx_demo (id, price) VALUES (2, 200)"
                ))

            second = count_expensive(reader)

    expected = 1 if level == "READ COMMITTED" else 0
    assert first == 0 and second == expected

    print(f"Phantom read [{level}]: {first} -> {second}")


# 4. SERIALIZABLE

def serializable():
    prepare()

    started = Event()
    finished = Event()
    errors = []

    def insert_row():
        try:
            with engine.begin() as writer:
                started.set()
                writer.execute(text(
                    "INSERT INTO tx_demo (id, price) VALUES (2, 200)"
                ))
        except Exception as exc:
            errors.append(exc)
        finally:
            finished.set()

    with engine.connect().execution_options(
        isolation_level="SERIALIZABLE"
    ) as reader:

        with reader.begin():
            first = count_expensive(reader)

            thread = Thread(target=insert_row)
            thread.start()
            started.wait()

            # The INSERT should wait for the reader's transaction.
            inserted_early = finished.wait(timeout=1)

            second = count_expensive(reader)

        # Reader committed, so the INSERT can now complete.

    thread.join(timeout=10)

    assert not errors, errors
    assert not inserted_early
    assert not thread.is_alive()
    assert first == 0 and second == 0

    with engine.connect() as db:
        final = count_expensive(db)

    assert final == 1
    print(f"Serializable: {first} -> {second}, after commit: {final}")


if __name__ == "__main__":
    dirty_read("READ UNCOMMITTED")
    dirty_read("READ COMMITTED")

    non_repeatable_read("READ COMMITTED")
    non_repeatable_read("REPEATABLE READ")

    phantom_read("READ COMMITTED")
    phantom_read("REPEATABLE READ")

    serializable()

    print("All transaction tests passed!")
