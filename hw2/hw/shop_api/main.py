from fastapi import FastAPI
from .api.carts.routes import router as carts_router
from .api.items.routes import router as items_router

app = FastAPI(title="Shop API")
app.include_router(carts_router)
app.include_router(items_router)
