from fastapi import FastAPI

from shop_api.item.routes import router as item_router
from shop_api.cart.routes import router as cart_router
app = FastAPI(title="Shop API")

app.include_router(item_router, prefix="/item", tags=["item"])
app.include_router(cart_router, prefix="/cart", tags=["cart"])
