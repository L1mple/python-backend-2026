"""Для демонстраций уровней изоляции"""
from sqlalchemy import Connection, text

from shop_api.db import engine

DEMO_PATTERN = "демо:%"


def connect(level: str) -> Connection:
    """Новое соединение; его транзакции идут на уровне изоляции level."""
    conn = engine.connect()
    conn.execution_options(isolation_level=level)
    return conn


def real_level(conn: Connection) -> str:
    """Какой уровень изоляции на самом деле у текущей транзакции — спрашиваем у Postgres."""
    return conn.execute(text("SHOW transaction_isolation")).scalar_one()


def cleanup() -> None:
    """Удалить демо-товары, чтобы каждый запуск начинался с чистого листа."""
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM items WHERE name LIKE :pattern"), {"pattern": DEMO_PATTERN})


def insert_item(conn: Connection, name: str, price: float) -> int:
    return conn.execute(
        text("INSERT INTO items (name, price, deleted) VALUES (:name, :price, false) RETURNING id"),
        {"name": name, "price": price},
    ).scalar_one()


def create_item(name: str, price: float) -> int:
    """Создать товар в отдельной транзакции, которая сразу коммитится."""
    with engine.begin() as conn:
        return insert_item(conn, name, price)


def get_price(conn: Connection, item_id: int) -> float:
    return conn.execute(
        text("SELECT price FROM items WHERE id = :id"), {"id": item_id}
    ).scalar_one()


def set_price(conn: Connection, item_id: int, price: float) -> None:
    conn.execute(
        text("UPDATE items SET price = :price WHERE id = :id"), {"price": price, "id": item_id}
    )


def count_items(conn: Connection, name: str) -> int:
    return conn.execute(
        text("SELECT count(*) FROM items WHERE name = :name"), {"name": name}
    ).scalar_one()
