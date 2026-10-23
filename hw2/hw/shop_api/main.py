from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from shop_api.database import create_schema
from shop_api.routes import router

create_schema()

app = FastAPI(title="Shop API")
Instrumentator().instrument(app).expose(app)
app.include_router(router)
