import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:7432/shop")
engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine)