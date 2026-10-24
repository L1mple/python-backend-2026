
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from store.database import create_tables

from shop_api.item import router as item_router
from shop_api.cart import router as cart_router
from shop_api.chat import router as chat_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield


app = FastAPI(
    title="Shop API",
    lifespan=lifespan,
)

Instrumentator().instrument(app).expose(app)

app.include_router(item_router)
app.include_router(cart_router)
app.include_router(chat_router)
