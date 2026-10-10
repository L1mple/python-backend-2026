from fastapi import FastAPI

from shop_api.routers import carts, chat, items

app = FastAPI(title="Shop API")

app.include_router(items.router)
app.include_router(carts.router)
app.include_router(chat.router)
