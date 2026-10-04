from fastapi import FastAPI

from .api.carts import router as carts_router
from .api.items import router as items_router

app = FastAPI(title="Shop API")

app.include_router(items_router)
app.include_router(carts_router)
