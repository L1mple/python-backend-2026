import os
import asyncio
from shop_api.database import _ensure_engine, Base
import shop_api.models  # noqa: F401

_db_url = os.environ.get("DATABASE_URL", "")
_is_sqlite = _db_url.startswith("sqlite") if _db_url else False


async def _init_db():
    engine = _ensure_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def pytest_configure(config):
    if _is_sqlite:
        try:
            asyncio.run(_init_db())
        except Exception:
            pass