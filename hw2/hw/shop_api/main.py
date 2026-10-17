from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from . import carts, chat, items

app = FastAPI(title="Shop API")

app.include_router(items.router)
app.include_router(carts.router)
app.include_router(chat.router)

Instrumentator(
    excluded_handlers=["^/metrics$", "^/docs$", "^/openapi.json$"],
).instrument(app).expose(app, include_in_schema=False)
