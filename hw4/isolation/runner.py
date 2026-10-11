import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock
from time import monotonic_ns

import jpype


@dataclass(frozen=True)
class Scenario:
    """Defines one isolation experiment and its expected observation."""

    name: str
    isolation: str
    level: int
    dirty: bool
    phantom: bool
    expected: int


SCENARIOS = (
    Scenario("dirty_ru", "READ_UNCOMMITTED", 1, True, False, 200),
    Scenario("dirty_rc", "READ_COMMITTED", 2, True, False, 100),
    Scenario("nonrepeatable_rc", "READ_COMMITTED", 2, False, False, 200),
    Scenario("nonrepeatable_rr", "REPEATABLE_READ", 4, False, False, 100),
    Scenario("phantom_rr", "REPEATABLE_READ", 4, False, True, 1),
    Scenario("phantom_serializable", "SERIALIZABLE", 8, False, True, 1),
)


class Journal:
    """Writes ordered transaction events with monotonic elapsed time."""

    def __init__(self, output):
        self.output = output
        self.started = monotonic_ns()
        self.sequence = 0
        self.lock = Lock()

    def record(self, scenario, transaction, event, value=None):
        with self.lock:
            self.sequence += 1
            row = {
                "seq": self.sequence,
                "case": scenario.name,
                "isolation": scenario.isolation,
                "tx": transaction,
                "event": event,
                "value": value,
                "elapsed_ms": (monotonic_ns() - self.started) / 1_000_000,
            }
            self.output.write(json.dumps(row) + "\n")
            self.output.flush()


class Coordination:
    """Orders two workers and releases waits when either worker fails."""

    def __init__(self, timeout=15):
        self.timeout = timeout
        self.first_read = Event()
        self.changed = Event()
        self.second_read = Event()
        self.finished = Event()
        self.failed = Event()

    def wait(self, event):
        if not event.wait(self.timeout):
            raise TimeoutError("transaction coordination timed out")
        if self.failed.is_set():
            raise RuntimeError("other transaction failed")

    def run(self, operation, *args):
        try:
            return operation(*args)
        except BaseException:
            self.failed.set()
            for event in (self.first_read, self.changed, self.second_read, self.finished):
                event.set()
            raise


class IsolationLab:
    """Runs six real two-transaction H2 experiments from Python."""

    def __init__(self, journal, jar):
        self.journal = journal
        if not jpype.isJVMStarted():
            jpype.startJVM(classpath=[str(jar)])
        self.driver = jpype.JClass("org.h2.Driver")()
        self.properties = jpype.JClass("java.util.Properties")()

    def connect(self, url, scenario=None):
        connection = self.driver.connect(url, self.properties)
        try:
            if scenario is not None:
                connection.setTransactionIsolation(scenario.level)
                connection.setAutoCommit(False)
                self.require(connection.getTransactionIsolation(), scenario.level)
            return connection
        except BaseException:
            connection.close()
            raise

    @staticmethod
    def require(actual, expected):
        if actual != expected:
            raise AssertionError(f"expected {expected}, observed {actual}")

    def run(self, scenario):
        url = f"jdbc:h2:mem:{scenario.name};DB_CLOSE_DELAY=-1;LOCK_TIMEOUT=5000"
        with closing(self.connect(url)) as setup, closing(setup.createStatement()) as sql:
            version = str(setup.getMetaData().getDatabaseProductVersion())
            if not version.startswith("2.5.252"):
                raise RuntimeError(f"expected H2 2.5.252, got {version}")
            sql.setQueryTimeout(15)
            sql.execute("CREATE TABLE accounts (id INT PRIMARY KEY, balance INT NOT NULL)")
            sql.execute("INSERT INTO accounts VALUES (1, 100)")
        coordination = Coordination()
        with ThreadPoolExecutor(max_workers=2) as workers:
            reader = workers.submit(coordination.run, self.read, scenario, url, coordination)
            writer = workers.submit(coordination.run, self.write, scenario, url, coordination)
            reader.result(timeout=30)
            writer.result(timeout=30)
        self.journal.record(scenario, "LAB", "PASS", scenario.expected)

    def scalar(self, connection, scenario):
        query = (
            "SELECT id, balance FROM accounts WHERE balance >= 100 ORDER BY id"
            if scenario.phantom
            else "SELECT balance FROM accounts WHERE id = 1"
        )
        with closing(connection.createStatement()) as sql:
            sql.setQueryTimeout(15)
            with closing(sql.executeQuery(query)) as result:
                if scenario.phantom:
                    count = 0
                    while result.next():
                        count += 1
                    return count
                if not result.next():
                    raise RuntimeError(f"missing scalar result: {scenario.name}")
                return int(result.getInt(1))

    def read(self, scenario, url, coordination):
        with closing(self.connect(url, scenario)) as connection:
            try:
                self.journal.record(scenario, "T1", "BEGIN")
                initial = self.scalar(connection, scenario)
                self.require(initial, 1 if scenario.phantom else 100)
                self.journal.record(scenario, "T1", "READ_1", initial)
                coordination.first_read.set()
                coordination.wait(coordination.changed)
                observed = self.scalar(connection, scenario)
                self.journal.record(scenario, "T1", "READ_2", observed)
                self.require(observed, scenario.expected)
                coordination.second_read.set()
                if scenario.dirty:
                    coordination.wait(coordination.finished)
                    restored = self.scalar(connection, scenario)
                    self.journal.record(scenario, "T1", "READ_AFTER_ROLLBACK", restored)
                    self.require(restored, 100)
                connection.commit()
                self.journal.record(scenario, "T1", "COMMIT")
            except BaseException:
                connection.rollback()
                raise

    def write(self, scenario, url, coordination):
        with closing(self.connect(url, scenario)) as connection:
            try:
                self.journal.record(scenario, "T2", "BEGIN")
                coordination.wait(coordination.first_read)
                query = (
                    "INSERT INTO accounts VALUES (2, 150)"
                    if scenario.phantom
                    else "UPDATE accounts SET balance = 200 WHERE id = 1"
                )
                with closing(connection.createStatement()) as sql:
                    sql.setQueryTimeout(15)
                    self.require(sql.executeUpdate(query), 1)
                self.journal.record(
                    scenario, "T2", "INSERT" if scenario.phantom else "UPDATE",
                    150 if scenario.phantom else 200,
                )
                if scenario.dirty:
                    coordination.changed.set()
                    coordination.wait(coordination.second_read)
                    connection.rollback()
                    self.journal.record(scenario, "T2", "ROLLBACK")
                    coordination.finished.set()
                else:
                    connection.commit()
                    self.journal.record(scenario, "T2", "COMMIT")
                    coordination.changed.set()
            except BaseException:
                connection.rollback()
                raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--jar", type=Path, default=Path("/lab/h2.jar"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as output:
        lab = IsolationLab(Journal(output), args.jar)
        for scenario in SCENARIOS:
            lab.run(scenario)
    print("H2 2.5.252: all six isolation assertions passed")
