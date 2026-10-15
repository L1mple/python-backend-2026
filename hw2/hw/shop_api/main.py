from fastapi import FastAPI

from shop_api.item import router as item_router
from shop_api.cart import router as cart_router
from shop_api.chat import router as chat_router

app = FastAPI(title="Shop API")

app.include_router(item_router)
app.include_router(cart_router)
app.include_router(chat_router)