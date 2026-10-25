import json
import threading
import time

from sqlalchemy import create_engine

from database import make_database_url


engine = create_engine(make_database_url())


def wait(event: threading.Event) -> None:
    if not event.wait(5):
        raise RuntimeError("Transaction did not reach the expected state")


def join(thread: threading.Thread, errors: list[BaseException]) -> None:
    thread.join(10)
    if thread.is_alive():
        raise RuntimeError("Transaction did not finish")
    if errors:
        raise errors[0]


def transaction(isolation_level: str):
    connection = engine.raw_connection()
    connection.autocommit(False)
    cursor = connection.cursor()
    cursor.execute(f"SET TRANSACTION ISOLATION LEVEL {isolation_level}")
    cursor.execute("SET LOCK_TIMEOUT 5000")
    return connection, cursor


def prepare() -> None:
    connection = engine.raw_connection()
    connection.autocommit(True)
    cursor = connection.cursor()
    try:
        cursor.execute("DROP TABLE IF EXISTS transaction_demo")
        cursor.execute("CREATE TABLE transaction_demo (id INT PRIMARY KEY, value INT NOT NULL)")
        cursor.execute("CREATE INDEX ix_transaction_demo_value ON transaction_demo (value)")
        cursor.execute("INSERT INTO transaction_demo (id, value) VALUES (1, 10)")
    finally:
        connection.close()


def read_value(cursor) -> int:
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("Transaction demo row is missing")
    return int(row[0])


def dirty_read(isolation_level: str) -> int:
    prepare()
    written = threading.Event()
    release = threading.Event()
    reader_started = threading.Event()
    reader_done = threading.Event()
    errors: list[BaseException] = []
    result: list[int] = []

    def writer() -> None:
        connection, cursor = transaction("READ COMMITTED")
        try:
            cursor.execute("UPDATE transaction_demo SET value = 20 WHERE id = 1")
            written.set()
            wait(release)
            connection.rollback()
        except BaseException as error:
            errors.append(error)
        finally:
            connection.close()

    def reader() -> None:
        connection, cursor = transaction(isolation_level)
        try:
            reader_started.set()
            cursor.execute("SELECT value FROM transaction_demo WHERE id = 1")
            result.append(read_value(cursor))
            connection.rollback()
        except BaseException as error:
            errors.append(error)
        finally:
            reader_done.set()
            connection.close()

    writer_thread = threading.Thread(target=writer)
    reader_thread = threading.Thread(target=reader)
    writer_thread.start()
    wait(written)
    reader_thread.start()
    wait(reader_started)
    if isolation_level == "READ COMMITTED":
        time.sleep(0.2)
        release.set()
    else:
        wait(reader_done)
        release.set()
    join(reader_thread, errors)
    join(writer_thread, errors)
    return result[0]


def non_repeatable_read(isolation_level: str) -> list[int]:
    prepare()
    first_read = threading.Event()
    writer_started = threading.Event()
    writer_done = threading.Event()
    errors: list[BaseException] = []
    result: list[int] = []

    def reader() -> None:
        connection, cursor = transaction(isolation_level)
        try:
            cursor.execute("SELECT value FROM transaction_demo WHERE id = 1")
            result.append(read_value(cursor))
            first_read.set()
            if isolation_level == "READ COMMITTED":
                wait(writer_done)
            else:
                wait(writer_started)
                time.sleep(0.2)
            cursor.execute("SELECT value FROM transaction_demo WHERE id = 1")
            result.append(read_value(cursor))
            connection.commit()
        except BaseException as error:
            errors.append(error)
        finally:
            connection.close()

    def writer() -> None:
        wait(first_read)
        connection, cursor = transaction("READ COMMITTED")
        try:
            writer_started.set()
            cursor.execute("UPDATE transaction_demo SET value = 20 WHERE id = 1")
            connection.commit()
            writer_done.set()
        except BaseException as error:
            errors.append(error)
        finally:
            connection.close()

    reader_thread = threading.Thread(target=reader)
    writer_thread = threading.Thread(target=writer)
    reader_thread.start()
    writer_thread.start()
    join(reader_thread, errors)
    join(writer_thread, errors)
    return result


def phantom_read(isolation_level: str) -> list[int]:
    prepare()
    first_read = threading.Event()
    writer_started = threading.Event()
    writer_done = threading.Event()
    errors: list[BaseException] = []
    result: list[int] = []

    def reader() -> None:
        connection, cursor = transaction(isolation_level)
        try:
            cursor.execute("SELECT COUNT(*) FROM transaction_demo WHERE value >= 10")
            result.append(read_value(cursor))
            first_read.set()
            if isolation_level == "REPEATABLE READ":
                wait(writer_done)
            else:
                wait(writer_started)
                time.sleep(0.2)
            cursor.execute("SELECT COUNT(*) FROM transaction_demo WHERE value >= 10")
            result.append(read_value(cursor))
            connection.commit()
        except BaseException as error:
            errors.append(error)
        finally:
            connection.close()

    def writer() -> None:
        wait(first_read)
        connection, cursor = transaction("READ COMMITTED")
        try:
            writer_started.set()
            cursor.execute("INSERT INTO transaction_demo (id, value) VALUES (2, 15)")
            connection.commit()
            writer_done.set()
        except BaseException as error:
            errors.append(error)
        finally:
            connection.close()

    reader_thread = threading.Thread(target=reader)
    writer_thread = threading.Thread(target=writer)
    reader_thread.start()
    writer_thread.start()
    join(reader_thread, errors)
    join(writer_thread, errors)
    return result


def run() -> dict[str, int | list[int]]:
    return {
        "dirty_read_read_uncommitted": dirty_read("READ UNCOMMITTED"),
        "dirty_read_read_committed": dirty_read("READ COMMITTED"),
        "non_repeatable_read_committed": non_repeatable_read("READ COMMITTED"),
        "non_repeatable_repeatable_read": non_repeatable_read("REPEATABLE READ"),
        "phantom_repeatable_read": phantom_read("REPEATABLE READ"),
        "phantom_serializable": phantom_read("SERIALIZABLE"),
    }


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
