from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from .database import create_db_and_tables
from .routes import router


app = FastAPI(title="Shop API")

app.include_router(router)

Instrumentator().instrument(app).expose(app)


@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()