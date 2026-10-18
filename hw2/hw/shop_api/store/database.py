import os

from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite+pysqlite:///:memory:')

if DATABASE_URL.startswith('sqlite'):
    engine = create_engine(
        DATABASE_URL,
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Item(Base):
    __tablename__ = 'items'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    price = Column(Float, nullable=False)
    deleted = Column(Boolean, default=False, nullable=False)


class Cart(Base):
    __tablename__ = 'carts'

    id = Column(Integer, primary_key=True)


class CartItem(Base):
    __tablename__ = 'cart_items'

    cart_id = Column(Integer, ForeignKey('carts.id'), primary_key=True)
    item_id = Column(Integer, ForeignKey('items.id'), primary_key=True)
    quantity = Column(Integer, nullable=False, default=1)


def init_db():
    Base.metadata.create_all(bind=engine)
