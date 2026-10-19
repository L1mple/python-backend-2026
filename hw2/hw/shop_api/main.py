import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from .api.carts import router as carts_router
from .api.items import router as items_router
from .store.database import IS_SQLITE, init_db


def _prepare_sqlite_for_tests() -> None:
    """
    `TestClient(app)` без `with` не запускает lifespan,
    поэтому для SQLite (тесты) таблицы создаём при импорте.
    Для Postgres — ждём lifespan, чтобы не создавать пул
    в «неправильном» event loop до старта uvicorn.
    """
    if not IS_SQLITE:
        return

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(init_db())


_prepare_sqlite_for_tests()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Shop API", lifespan=lifespan)

app.include_router(items_router)
app.include_router(carts_router)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")
