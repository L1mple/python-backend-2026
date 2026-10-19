from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from .routes import router

app = FastAPI(title="Shop API")

app.include_router(router)
Instrumentator().instrument(app).expose(app)
