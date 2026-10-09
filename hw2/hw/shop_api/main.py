from fastapi import FastAPI

from shop_api.item.routes import router as item_router
from shop_api.cart.routes import router as cart_router
from shop_api.chat.routes import router as chat_router
from prometheus_fastapi_instrumentator import Instrumentator
app = FastAPI(title="Shop API")

app.include_router(item_router, prefix="/item", tags=["item"])
app.include_router(cart_router, prefix="/cart", tags=["cart"])
app.include_router(chat_router, prefix="/chat", tags=["chat"])

Instrumentator(
    excluded_handlers=["/metrics"]
).instrument(app).expose(app)