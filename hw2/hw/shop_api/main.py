from fastapi import FastAPI

from . import carts, chat, items

app = FastAPI(title="Shop API")

app.include_router(items.router)
app.include_router(carts.router)
app.include_router(chat.router)
