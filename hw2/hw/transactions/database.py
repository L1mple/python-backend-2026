import sqlite3
from pathlib import Path

from sqlalchemy import Float, Integer, String, create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

DATA_DIR.mkdir(parents=True, exist_ok=True)

NORMAL_DB_PATH = DATA_DIR / "transactions.db"
DIRTY_DB_PATH = DATA_DIR / "dirty_read.db"


with sqlite3.connect(NORMAL_DB_PATH) as connection:
    connection.execute("PRAGMA journal_mode=WAL")


engine = create_engine(
    f"sqlite:///{NORMAL_DB_PATH.as_posix()}",
    connect_args={
        "check_same_thread": False,
        "timeout": 10,
        "autocommit": False,
    },
    poolclass=None,
)


dirty_url = URL.create(
    "sqlite+pysqlite",
    database=f"file:{DIRTY_DB_PATH.as_posix()}",
    query={
        "cache": "shared",
        "uri": "true",
    },
)

dirty_engine = create_engine(
    dirty_url,
    connect_args={
        "check_same_thread": False,
        "timeout": 10,
        "autocommit": False,
    },
    poolclass=None,
)


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    price: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )


SessionLocal = sessionmaker(
    bind=engine,
    expire_on_commit=False,
)

DirtySessionLocal = sessionmaker(
    bind=dirty_engine,
    expire_on_commit=False,
)


def init_db() -> None:
    Base.metadata.create_all(engine)
    Base.metadata.create_all(dirty_engine)


def reset_db() -> None:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    Base.metadata.drop_all(dirty_engine)
    Base.metadata.create_all(dirty_engine)


if __name__ == "__main__":
    init_db()

    print("Databases initialized successfully!")
    print(f"Normal database: {NORMAL_DB_PATH}")
    print(f"Dirty read database: {DIRTY_DB_PATH}")