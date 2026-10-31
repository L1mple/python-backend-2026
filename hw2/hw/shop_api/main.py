from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from shop_api import router_items, router_cart
from store.database import Base, engine
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Shop API", lifespan=lifespan)
app.include_router(router_items.router)
app.include_router(router_cart.router)

Instrumentator().instrument(app).expose(app)
