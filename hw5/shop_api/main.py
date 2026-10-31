from contextlib import asynccontextmanager

from fastapi import FastAPI

from shop_api import models  # noqa: F401  (регистрирует таблицы в Base.metadata)
from shop_api.carts import router as cart_router
from shop_api.db import Base, engine
from shop_api.items import router as item_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Shop API", lifespan=lifespan)

app.include_router(cart_router)
app.include_router(item_router)
