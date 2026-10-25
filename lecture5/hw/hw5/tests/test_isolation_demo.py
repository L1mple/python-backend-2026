from __future__ import annotations

from contextlib import contextmanager

from hw import isolation_demo


class Result:
    def __init__(self, value=None):
        self.value = value

    def scalar(self):
        return self.value


class Transaction:
    def rollback(self):
        pass


class Connection:
    def __init__(self):
        self.select_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def begin(self):
        return Transaction()

    def execution_options(self, **kwargs):
        return self

    def execute(self, statement, parameters=None):
        sql = str(statement)
        if "count(*)" in sql:
            self.select_calls += 1
            return Result(0 if self.select_calls == 1 else 1)
        if "SELECT value" in sql:
            self.select_calls += 1
            return Result(1 if self.select_calls == 1 else 2)
        return Result()

    def commit(self):
        pass


class Engine:
    def connect(self):
        return Connection()

    @contextmanager
    def begin(self):
        yield Connection()


def test_isolation_examples_with_fake_engine(monkeypatch):
    monkeypatch.setattr(isolation_demo, "engine", Engine())

    assert isolation_demo.run_two_transactions(
        "READ COMMITTED", "SELECT value FROM isolation_demo"
    ) == (1, 2)
    assert isolation_demo.run_dirty_read() == (1, 2)
    assert isolation_demo.run_phantom("SERIALIZABLE") == (0, 1)


def test_main_prints_all_isolation_examples(monkeypatch, capsys):
    monkeypatch.setattr(isolation_demo, "engine", Engine())
    isolation_demo.main()
    output = capsys.readouterr().out
    assert "dirty read" in output
    assert "non-repeatable read" in output
    assert "phantom reads prevented" in output
