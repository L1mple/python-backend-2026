from fastapi import FastAPI

from shop_api.cart import router as cart_router
from shop_api.item import router as item_router

app = FastAPI(title="Shop API")

app.include_router(item_router, prefix="/item", tags=["item"])
app.include_router(cart_router, prefix="/cart", tags=["cart"])
