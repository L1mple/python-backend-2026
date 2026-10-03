from sqlalchemy import create_engine
from .models import Base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql+psycopg://postgres:abobaPOST@localhost:5432/shop_api"

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine)

Base.metadata.create_all(engine) # создает таблицы в бд

