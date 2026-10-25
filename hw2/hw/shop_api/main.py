from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from shop_api.api import cart_router, item_router
from shop_api.store.db import init_db

init_db()

app = FastAPI(title="Shop API")

app.include_router(item_router)
app.include_router(cart_router)

Instrumentator().instrument(app).expose(app)
