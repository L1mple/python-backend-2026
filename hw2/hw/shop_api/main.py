from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from .api.carts import router as carts_router
from .api.items import router as items_router

app = FastAPI(title="Shop API")

app.include_router(items_router)
app.include_router(carts_router)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")
