from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from . import carts, chat, database, items


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.initialize()
    try:
        yield
    finally:
        database.engine.dispose()


app = FastAPI(title="Shop API", lifespan=lifespan)

app.include_router(items.router)
app.include_router(carts.router)
app.include_router(chat.router)

Instrumentator(
    excluded_handlers=["^/metrics$", "^/docs$", "^/openapi.json$"],
).instrument(app).expose(app, include_in_schema=False)
