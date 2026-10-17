"""
Общие утилиты для демо-скриптов уровней изоляции транзакций.

Подключаемся напрямую через PyMySQL (а не через SQLAlchemy из
shop_api/db.py), чтобы иметь полный контроль над уровнем изоляции
конкретного соединения и моментом COMMIT/ROLLBACK каждой из двух
параллельных "сессий".

Используют отдельные от API таблицы (demo_accounts, demo_products) в той
же базе, чтобы не пересекаться с данными shop_api.
"""
import os

import pymysql
from pymysql.connections import Connection

DB_HOST = os.getenv("DEMO_DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DEMO_DB_PORT", "3307"))
DB_USER = os.getenv("DEMO_DB_USER", "shop")
DB_PASSWORD = os.getenv("DEMO_DB_PASSWORD", "shop")
DB_NAME = os.getenv("DEMO_DB_NAME", "shop_api")

_ISOLATION_LEVELS = {
    "READ UNCOMMITTED",
    "READ COMMITTED",
    "REPEATABLE READ",
    "SERIALIZABLE",
}


def connect(isolation_level: str | None = None) -> Connection:
    """Новое соединение со своей собственной транзакцией (autocommit выключен)."""
    conn = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        autocommit=False,
    )
    if isolation_level is not None:
        if isolation_level not in _ISOLATION_LEVELS:
            raise ValueError(f"Unknown isolation level: {isolation_level}")
        # Уровень изоляции должен быть выставлен до начала транзакции,
        # поэтому делаем это сразу после коннекта, перед первым запросом.
        with conn.cursor() as cur:
            cur.execute(f"SET SESSION TRANSACTION ISOLATION LEVEL {isolation_level}")
    return conn


def _autocommit_connection() -> Connection:
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        autocommit=True,
    )


def ensure_demo_schema() -> None:
    """Создаёт таблицы, которые используют демо-скрипты (если их ещё нет)."""
    conn = _autocommit_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS demo_accounts (
                    id INT PRIMARY KEY,
                    balance INT NOT NULL
                ) ENGINE=InnoDB
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS demo_products (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    price INT NOT NULL
                ) ENGINE=InnoDB
                """
            )
    finally:
        conn.close()


def reset_accounts(balance: int = 1000) -> None:
    conn = _autocommit_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM demo_accounts")
            cur.execute("INSERT INTO demo_accounts (id, balance) VALUES (1, %s)", (balance,))
    finally:
        conn.close()


def reset_products(seed_prices: list[int]) -> None:
    conn = _autocommit_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM demo_products")
            for price in seed_prices:
                cur.execute("INSERT INTO demo_products (price) VALUES (%s)", (price,))
    finally:
        conn.close()
