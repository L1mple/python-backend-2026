from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from shop_api.api import cart, item

app = FastAPI(title="Shop API")

Instrumentator().instrument(app).expose(app)

app.include_router(item.router)
app.include_router(cart.router)
