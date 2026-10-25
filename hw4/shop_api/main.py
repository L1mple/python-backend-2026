from contextlib import asynccontextmanager

from fastapi import FastAPI
from .routes import router2
from .store.db import create_tables

from prometheus_fastapi_instrumentator import Instrumentator


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield


app = FastAPI(title="Shop API", lifespan=lifespan)
app.include_router(router2)

Instrumentator().instrument(app).expose(app)
