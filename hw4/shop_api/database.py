from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from shop_api.config import DATABASE_URL


def create_engine(url: str = DATABASE_URL, **kwargs) -> AsyncEngine:
    return create_async_engine(url, **kwargs)


engine = create_engine()
session_factory = async_sessionmaker(engine, expire_on_commit=False)
