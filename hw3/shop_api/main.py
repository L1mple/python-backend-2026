from fastapi import FastAPI
from .routes import router2

from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter

app = FastAPI(title="Shop API")
app.include_router(router2)

Instrumentator().instrument(app).expose(app)