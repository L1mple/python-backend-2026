from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from shop_api import router_items, router_cart
app = FastAPI(title="Shop API")
app.include_router(router_items.router)
app.include_router(router_cart.router)

Instrumentator().instrument(app).expose(app)
