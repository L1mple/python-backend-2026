import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://shop_app:shop_local@localhost:5433/shop_db",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session():
    with SessionLocal() as session:
        yield session


def create_tables():
    Base.metadata.create_all(engine)