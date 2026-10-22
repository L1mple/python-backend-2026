from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from shop_api.carts import router as cart_router
from shop_api.items import router as item_router

app = FastAPI(title="Shop API")

app.include_router(cart_router)
app.include_router(item_router)

# Ручка /metrics для Prometheus: дефолтные метрики запросов (количество, статусы, латентность)
Instrumentator().instrument(app).expose(app)
