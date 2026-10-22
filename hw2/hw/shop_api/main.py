from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from shop_api.routers import carts, chat, items

app = FastAPI(title="Shop API")

app.include_router(items.router)
app.include_router(carts.router)
app.include_router(chat.router)

# Стандартные корзины задержек (0.1, 0.5, 1 с) слишком грубые для запросов,
# которые отвечают за миллисекунды, поэтому задаём свои
Instrumentator(excluded_handlers=["/metrics"]).instrument(
    app,
    latency_lowr_buckets=(0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1),
).expose(app, include_in_schema=False)
