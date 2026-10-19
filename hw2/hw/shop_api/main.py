from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from shop_api.api import carts_router, items_router

app = FastAPI(title="Shop API")

app.include_router(items_router)
app.include_router(carts_router)

Instrumentator().instrument(app).expose(app)