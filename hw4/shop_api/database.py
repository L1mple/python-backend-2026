import os
from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row

DEFAULT_DATABASE_URL = "postgresql://shop:shop@localhost:7433/shop"


def database_url() -> str:
    return os.environ.get("SHOP_DATABASE_URL", DEFAULT_DATABASE_URL)


def connect() -> Connection:
    return psycopg.connect(database_url(), row_factory=dict_row)


@contextmanager
def session() -> Iterator[Connection]:
    with connect() as connection:
        yield connection


def initialize() -> None:
    with session() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS items (
                sequence BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                id UUID NOT NULL UNIQUE,
                name TEXT NOT NULL,
                price DOUBLE PRECISION NOT NULL CHECK (price >= 0),
                deleted BOOLEAN NOT NULL DEFAULT FALSE
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS carts (
                sequence BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                id UUID NOT NULL UNIQUE
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS cart_items (
                sequence BIGINT GENERATED ALWAYS AS IDENTITY,
                cart_id UUID NOT NULL REFERENCES carts(id),
                item_id UUID NOT NULL REFERENCES items(id),
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                PRIMARY KEY (cart_id, item_id)
            )
        """)
