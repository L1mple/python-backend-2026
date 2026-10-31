import os
from pathlib import Path

from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool


database_file = Path(__file__).resolve().parent.parent / "shop.db"
# В Docker адрес PostgreSQL приходит из compose. Без него работаем с файлом SQLite.
database_url = os.getenv("SHOP_DATABASE_URL", f"sqlite:///{database_file.as_posix()}")
if database_url in ("sqlite://", "sqlite:///:memory:"):
    # В тестах все сессии должны видеть одну и ту же SQLite-БД в памяти.
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
elif database_url.startswith("sqlite"):
    # Обычный локальный запуск: данные сохраняются в файле SQLite.
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
else:
    # Запуск с PostgreSQL, например через Docker Compose.
    engine = create_engine(database_url)

if engine.dialect.name == "sqlite":
    # SQLite требует отдельно включить проверку ForeignKey на каждом соединении.
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, connection_record):
        connection.execute("PRAGMA foreign_keys=ON")

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
# SessionLocal() создаёт сессию. После commit поля объекта остаются доступными.
Base = declarative_base()


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    deleted = Column(Boolean, nullable=False, default=False)


class Cart(Base):
    __tablename__ = "carts"

    id = Column(Integer, primary_key=True)


class CartItem(Base):
    __tablename__ = "cart_items"

    cart_id = Column(Integer, ForeignKey("carts.id"), primary_key=True)
    item_id = Column(Integer, ForeignKey("items.id"), primary_key=True)
    quantity = Column(Integer, nullable=False, default=1)


# Создаём таблицы и при обычном запуске, и при импорте из тестов преподавателя.
Base.metadata.create_all(engine)
