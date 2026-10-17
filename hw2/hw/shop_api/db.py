"""
hw4: слой хранения на MySQL для shop_api (вместо словарей в памяти).

Адрес БД берётся из переменной окружения DATABASE_URL. По умолчанию
указывает на порт, на котором MySQL торчит наружу из docker-compose
(см. hw3/docker-compose.yml) - то есть локальный `pytest` без Docker-сети
тоже сможет подключиться, если поднять контейнер mysql.
"""
import os
from typing import Optional

from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://shop:shop@localhost:3307/shop_api",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

Base = declarative_base()


class ItemOrm(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    price = Column(Float, nullable=False)
    deleted = Column(Boolean, nullable=False, default=False)


class CartOrm(Base):
    __tablename__ = "carts"

    id = Column(Integer, primary_key=True, autoincrement=True)


class CartItemOrm(Base):
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cart_id = Column(Integer, ForeignKey("carts.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=0)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    return SessionLocal()
