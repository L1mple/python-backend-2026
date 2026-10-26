from __future__ import annotations

from sqlalchemy import Connection, text

from store.db import engine


def connect(level: str) -> Connection:
    return engine.connect().execution_options(isolation_level=level)


def reset_accounts(*rows: tuple[str, int]) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS accounts ("
                "id SERIAL PRIMARY KEY, owner TEXT NOT NULL, balance INTEGER NOT NULL)"
            )
        )
        conn.execute(text("TRUNCATE accounts RESTART IDENTITY"))
        conn.execute(
            text("INSERT INTO accounts (owner, balance) VALUES (:owner, :balance)"),
            [{"owner": owner, "balance": balance} for owner, balance in rows],
        )


def balance(conn: Connection, owner: str) -> int:
    return conn.execute(
        text("SELECT balance FROM accounts WHERE owner = :owner"),
        {"owner": owner},
    ).scalar_one()


def verdict(anomaly: bool) -> str:
    return "аномалия есть" if anomaly else "аномалии нет"
