import os

from sqlmodel import SQLModel, Session, create_engine
from . import db_models


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://shop:shop@localhost:5432/shop",
)

engine = create_engine(DATABASE_URL)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)