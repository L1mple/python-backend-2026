from fastapi import FastAPI

from shop_api.routes.cart import router as cart_router
from shop_api.routes.item import router as item_router

app = FastAPI(title="Shop API")

app.include_router(cart_router)
app.include_router(item_router)